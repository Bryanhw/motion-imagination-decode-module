"""Regression checks for real pygame key events at the game entry point."""

import importlib
import os
import unittest
from unittest.mock import patch

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

game_main = importlib.import_module("game.platformer.main")
pygame = game_main.pygame
RealGameController = game_main.GameController


class MainKeyboardEventTests(unittest.TestCase):
    def run_events(self, mode, frames):
        games = []

        class TrackingGame(RealGameController):
            def __init__(self):
                super().__init__()
                self.intents = []
                games.append(self)

            def update(self, intent, dt):
                self.intents.append(intent)
                super().update(intent, dt)

        class NoConnection:
            def __init__(self, url):
                pass

            def start(self):
                pass

            def poll(self):
                return []

            def stop(self):
                pass

        events = iter(frames)
        with patch.object(game_main, "GameController", TrackingGame), \
             patch.object(game_main, "WebSocketInputAdapter", NoConnection), \
             patch.object(pygame.event, "get", side_effect=lambda: next(events, [pygame.event.Event(pygame.QUIT)])):
            self.assertEqual(game_main.main(["--mode", mode]), 0)
        return games[0]

    def test_d_keydown_without_repeat_jumps_once(self):
        game = self.run_events("keyboard", [
            [pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RETURN)],
            [pygame.event.Event(pygame.KEYDOWN, key=pygame.K_d)],
            [pygame.event.Event(pygame.KEYDOWN, key=pygame.K_d)],
            [pygame.event.Event(pygame.KEYDOWN, key=pygame.K_d, repeat=True)],
            [pygame.event.Event(pygame.QUIT)],
        ])
        self.assertEqual(game.intents.count("RIGHT_HAND"), 1)
        self.assertFalse(game.player.grounded)

    def test_d_keydown_does_not_drive_websocket_mode(self):
        game = self.run_events("ws", [
            [pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RETURN)],
            [pygame.event.Event(pygame.KEYDOWN, key=pygame.K_d)],
            [pygame.event.Event(pygame.QUIT)],
        ])
        self.assertNotIn("RIGHT_HAND", game.intents)

    def test_w_key_events_move_and_stop_without_key_state_polling(self):
        game = self.run_events("keyboard", [
            [pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RETURN)],
            [pygame.event.Event(pygame.KEYDOWN, key=pygame.K_w)],
            [],
            [pygame.event.Event(pygame.KEYUP, key=pygame.K_w)],
            [],
            [pygame.event.Event(pygame.QUIT)],
        ])
        self.assertEqual(game.intents[:3], ["NONE", "LEFT_HAND", "LEFT_HAND"])
        self.assertEqual(game.intents[-2:], ["NONE", "NONE"])
        self.assertGreater(game.player.x, 28)

    def test_d_key_events_jump_and_rearm_after_release(self):
        game = self.run_events("keyboard", [
            [pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RETURN)],
            [pygame.event.Event(pygame.KEYDOWN, key=pygame.K_d)],
            [pygame.event.Event(pygame.KEYDOWN, key=pygame.K_d)],
            [pygame.event.Event(pygame.KEYUP, key=pygame.K_d)],
            [pygame.event.Event(pygame.KEYDOWN, key=pygame.K_d)],
            [pygame.event.Event(pygame.QUIT)],
        ])
        self.assertEqual(game.intents.count("RIGHT_HAND"), 2)

    def test_physical_keys_work_when_ime_changes_key_symbols(self):
        game = self.run_events("keyboard", [
            [pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RETURN)],
            [pygame.event.Event(pygame.KEYDOWN, key=pygame.K_UNKNOWN, scancode=pygame.KSCAN_W)],
            [],
            [pygame.event.Event(pygame.KEYUP, key=pygame.K_UNKNOWN, scancode=pygame.KSCAN_W)],
            [pygame.event.Event(pygame.KEYDOWN, key=pygame.K_UNKNOWN, scancode=pygame.KSCAN_D)],
            [pygame.event.Event(pygame.KEYUP, key=pygame.K_UNKNOWN, scancode=pygame.KSCAN_D)],
            [pygame.event.Event(pygame.QUIT)],
        ])
        self.assertIn("LEFT_HAND", game.intents)
        self.assertEqual(game.intents.count("RIGHT_HAND"), 1)
        self.assertEqual(game.intents[-1], "NONE")

    def test_control_window_disables_text_composition_on_start_and_refocus(self):
        with patch.object(pygame.key, "stop_text_input") as stop_text:
            self.run_events("keyboard", [
                [pygame.event.Event(pygame.WINDOWFOCUSGAINED)],
                [pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RETURN)],
                [pygame.event.Event(pygame.QUIT)],
            ])
        self.assertGreaterEqual(stop_text.call_count, 2)

    def test_focus_loss_releases_w(self):
        game = self.run_events("keyboard", [
            [pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RETURN)],
            [pygame.event.Event(pygame.KEYDOWN, key=pygame.K_w)],
            [pygame.event.Event(pygame.WINDOWFOCUSLOST)],
            [pygame.event.Event(pygame.QUIT)],
        ])
        self.assertEqual(game.intents[-1], "NONE")


class MainCameraRenderingTests(unittest.TestCase):
    def test_player_follows_camera_and_stands_on_scrolled_platform(self):
        pygame.init()
        try:
            game = RealGameController()
            game.player.x = 250
            game.player.y = 80
            camera = int(game.player.x - 88)
            surface = pygame.Surface((320, 180))
            game_main.draw_scene(surface, game, camera, "NONE", "TEST", 0)
            player_screen_x = int(game.player.x - camera)
            self.assertEqual(tuple(surface.get_at((player_screen_x + 4, 81)))[:3], game_main.PINK)
            self.assertEqual(tuple(surface.get_at((player_screen_x + 4, 96)))[:3], game_main.GRASS)
            self.assertNotEqual(tuple(surface.get_at((int(game.player.x) + 4, 81)))[:3], game_main.PINK)
        finally:
            pygame.quit()


if __name__ == "__main__":
    unittest.main()
