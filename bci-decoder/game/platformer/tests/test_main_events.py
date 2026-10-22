"""Regression checks for real pygame key events at the game entry point."""

import importlib
import os
import unittest
from collections import defaultdict
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
        held_keys = defaultdict(bool, {pygame.K_d: True})
        with patch.object(game_main, "GameController", TrackingGame), \
             patch.object(game_main, "WebSocketInputAdapter", NoConnection), \
             patch.object(pygame.event, "get", side_effect=lambda: next(events, [pygame.event.Event(pygame.QUIT)])), \
             patch.object(pygame.key, "get_pressed", return_value=held_keys):
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


if __name__ == "__main__":
    unittest.main()
