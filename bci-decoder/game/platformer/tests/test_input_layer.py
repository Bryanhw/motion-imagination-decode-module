"""Small standard-library unittest suite for the input contract and controller."""

import unittest

from game.platformer.input_layer import Decision, DecisionReceiver, KeyboardInputAdapter
from game.platformer.physics import GameController


def apply(adapter, receiver, controller, w, d, now, dt=0.016):
    for decision in adapter.poll(w, d, now):
        receiver.receive(decision, now)
    controller.update(receiver.current(now).intent, dt)


class InputContractTests(unittest.TestCase):
    def setUp(self):
        self.keyboard = KeyboardInputAdapter()
        self.receiver = DecisionReceiver(timeout=0.5)
        self.game = GameController()

    def test_w_held_moves_forward_continuously(self):
        for tick in range(30):
            apply(self.keyboard, self.receiver, self.game, True, False, tick / 60)
        self.assertGreater(self.game.player.x, 28)

    def test_releasing_w_stops_active_movement(self):
        for tick in range(30):
            apply(self.keyboard, self.receiver, self.game, True, False, tick / 60)
        apply(self.keyboard, self.receiver, self.game, False, False, 1.0)
        x = self.game.player.x
        apply(self.keyboard, self.receiver, self.game, False, False, 1.016)
        self.assertAlmostEqual(self.game.player.x, x)

    def test_held_d_jumps_once(self):
        apply(self.keyboard, self.receiver, self.game, False, True, 0)
        self.assertFalse(self.game.player.grounded)
        first_vy = self.game.player.vy
        jump_edges = 1
        for tick in range(1, 50):
            events = self.keyboard.poll(False, True, tick / 60)
            jump_edges += sum(event.intent == "RIGHT_HAND" for event in events)
            for event in events:
                self.receiver.receive(event, tick / 60)
            self.game.update(self.receiver.current(tick / 60).intent, 0.016)
        self.assertLess(first_vy, 0)
        self.assertGreater(self.game.player.vy, first_vy)
        self.assertEqual(jump_edges, 1)

    def test_jump_keeps_forward_inertia_when_only_right_hand_arrives(self):
        self.game.update("RIGHT_HAND", 1 / 60)
        start_x = self.game.player.x
        for _ in range(15):
            self.game.update("NONE", 1 / 60)
        self.assertGreater(self.game.player.x - start_x, 15)
        self.assertLess(self.game.player.vy, 0)

    def test_one_d_tap_after_wall_push_alone_jumps_over_obstacle(self):
        now = 0.0
        for tick in range(300):
            now += 1 / 60
            apply(self.keyboard, self.receiver, self.game, True, False, now)
            if self.game.player.x == 335 - 16:
                break
        self.assertEqual(self.game.player.x, 319)

        # Release W, tap D once, then provide no more active input.
        now += 1 / 60
        apply(self.keyboard, self.receiver, self.game, False, False, now)
        now += 1 / 60
        self.receiver.receive(self.keyboard.press_jump(now), now)
        self.game.update(self.receiver.current(now).intent, 1 / 60)
        for _ in range(90):
            now += 1 / 60
            for decision in self.keyboard.poll(False, False, now):
                self.receiver.receive(decision, now)
            self.game.update(self.receiver.current(now).intent, 1 / 60)

        self.assertGreaterEqual(self.game.player.x, 335 + 16)
        self.assertTrue(self.game.player.grounded)
        self.assertEqual(self.game.player.y, 128)

    def test_simultaneous_w_and_d_preserves_jump_then_forward_state(self):
        first = self.keyboard.poll(True, True, 0.0)
        self.assertEqual([event.intent for event in first], ["RIGHT_HAND"])
        second = self.keyboard.poll(True, True, 0.016)
        self.assertEqual([event.intent for event in second], ["LEFT_HAND"])

    def test_jump_edge_returns_to_none_before_next_jump_can_trigger(self):
        self.assertEqual([d.intent for d in self.keyboard.poll(False, True, 0.0)], ["RIGHT_HAND"])
        self.assertEqual([d.intent for d in self.keyboard.poll(False, True, 0.016)], ["NONE"])
        self.assertEqual(self.keyboard.poll(False, True, 0.032), [])
        self.assertEqual(self.keyboard.poll(False, False, 0.048), [])
        self.assertEqual([d.intent for d in self.keyboard.poll(False, True, 0.064)], ["RIGHT_HAND"])

    def test_jump_can_land_on_upper_platform(self):
        self.game.player.x = 85
        self.game.update("RIGHT_HAND", 1 / 60)
        for _ in range(80):
            self.game.update("NONE", 1 / 60)
        self.assertTrue(self.game.player.grounded)
        self.assertEqual(self.game.player.y, 80)
        self.assertGreater(self.game.player.x, 112)

    def test_jump_clears_obstacle_and_can_stand_on_its_top(self):
        self.game.player.x = 280
        self.game.update("RIGHT_HAND", 1 / 60)
        for _ in range(80):
            self.game.update("NONE", 1 / 60)
        self.assertGreaterEqual(self.game.player.x, 335)
        self.assertTrue(self.game.player.grounded)
        self.assertEqual(self.game.player.y, 128)

        self.game.reset()
        self.game.player.x = 260
        self.game.update("RIGHT_HAND", 1 / 60)
        for _ in range(80):
            self.game.update("NONE", 1 / 60)
        self.assertTrue(self.game.player.grounded)
        self.assertEqual(self.game.player.y, 112)

    def test_holding_forward_at_wall_then_one_jump_clears_obstacle(self):
        self.game.player.x = 310
        for _ in range(20):
            self.game.update("LEFT_HAND", 0.05)
        self.assertEqual(self.game.player.x, 319)
        # Simulate one low-frequency RIGHT_HAND result followed by no more forward results.
        self.game.update("RIGHT_HAND", 0.05)
        for _ in range(40):
            self.game.update("NONE", 0.05)
        self.assertGreaterEqual(self.game.player.x, 335 + 16)
        self.assertTrue(self.game.player.grounded)

    def test_duplicate_or_out_of_order_sequence_is_ignored(self):
        message = Decision(1, 5, "LEFT_HAND", "replay", 1.0)
        self.assertTrue(self.receiver.receive(message, received_at=1.0))
        self.assertFalse(self.receiver.receive(message, received_at=1.1))
        self.assertFalse(self.receiver.receive(Decision(1, 4, "RIGHT_HAND", "replay", 1.2), received_at=1.2))
        self.assertEqual(self.receiver.state.intent, "LEFT_HAND")

    def test_stale_remote_input_expires(self):
        self.receiver.receive(Decision(1, 1, "LEFT_HAND", "device", 9999.0), received_at=10.0)
        self.assertEqual(self.receiver.current(10.2).intent, "LEFT_HAND")
        self.assertEqual(self.receiver.current(10.51).intent, "NONE")

    def test_none_does_not_trigger_jump_or_forward(self):
        self.game.update("NONE", 0.016)
        x = self.game.player.x
        self.assertTrue(self.game.player.grounded)
        self.assertAlmostEqual(self.game.player.x, x)

    def test_lower_route_has_collectible_coins(self):
        lower = [(x, y) for x, y in self.game.coins if y >= 120]
        upper = [(x, y) for x, y in self.game.coins if y < 120]
        self.assertEqual(len(lower), 3)
        self.assertEqual(len(upper), 3)
        for tick in range(50):
            self.game.update("LEFT_HAND", 1 / 60)
        self.assertIn(0, self.game.collected)


if __name__ == "__main__":
    unittest.main()
