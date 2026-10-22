"""Checks for the decoder-to-game WebSocket message mapping."""

import json
import threading
import unittest
from unittest.mock import patch

from game.platformer.websocket_input import WebSocketInputAdapter, parse_decoder_output


def decoder_message(label="left", label_id=0, state="running"):
    return {
        "t_data": 12.5,
        "t_wall": 234.5,
        "label": label,
        "label_id": label_id,
        "confidence": 0.9,
        "probs": [0.9, 0.1],
        "state": state,
        "compute_ms": 1.2,
        "window_seconds": 2.0,
    }


class WebSocketMessageTests(unittest.TestCase):
    def test_maps_decoder_left_and_right_labels(self):
        left = parse_decoder_output(json.dumps(decoder_message()), sequence=4)
        right = parse_decoder_output(json.dumps(decoder_message("right", 1)), sequence=5)
        self.assertEqual((left.intent, left.source, left.sequence), ("LEFT_HAND", "device", 4))
        self.assertEqual((right.intent, right.source, right.sequence), ("RIGHT_HAND", "device", 5))

    def test_idle_and_non_running_state_never_drive_movement(self):
        idle = parse_decoder_output(json.dumps(decoder_message("idle", -1)), sequence=0)
        stabilizing = parse_decoder_output(json.dumps(decoder_message(state="stabilizing")), sequence=1)
        self.assertEqual(idle.intent, "NONE")
        self.assertEqual(stabilizing.intent, "NONE")

    def test_rejects_contract_changes_and_inconsistent_labels(self):
        changed = decoder_message()
        changed["extra"] = True
        with self.assertRaisesRegex(ValueError, "9 字段契约"):
            parse_decoder_output(json.dumps(changed), sequence=0)
        with self.assertRaisesRegex(ValueError, "label 与 label_id"):
            parse_decoder_output(json.dumps(decoder_message("left", 1)), sequence=0)


class WebSocketReconnectTests(unittest.TestCase):
    def test_reconnects_and_resets_sequence_after_connection_loss(self):
        adapter = WebSocketInputAdapter("ws://decoder.invalid", reconnect_seconds=0.01)
        attempts = 0
        first_disconnected = threading.Event()
        original_connect = __import__("websockets").connect

        class FakeConnection:
            def __init__(self, label, label_id, disconnect_event=None):
                self.label, self.label_id = label, label_id
                self.disconnect_event = disconnect_event

            async def __aenter__(self):
                return self

            async def __aexit__(self, *_):
                if self.disconnect_event:
                    self.disconnect_event.set()

            def __aiter__(self):
                async def messages():
                    yield json.dumps(decoder_message(self.label, self.label_id))
                return messages()

        def connect(*_args, **_kwargs):
            nonlocal attempts
            attempts += 1
            if attempts == 1:
                return FakeConnection("left", 0, first_disconnected)
            if attempts == 2:
                return FakeConnection("right", 1)
            raise AssertionError("应在第二次连接后停止")

        with patch.object(__import__("websockets"), "connect", connect):
            adapter.start()
            try:
                self.assertTrue(first_disconnected.wait(2))
                deadline = __import__("time").monotonic() + 2
                received = []
                while len([e for e in received if e[0] == "decision"]) < 2 and __import__("time").monotonic() < deadline:
                    received.extend(adapter.poll())
                    __import__("time").sleep(0.01)
                decisions = [e[1] for e in received if e[0] == "decision"]
                self.assertEqual([(d.intent, d.sequence) for d in decisions],
                                 [("LEFT_HAND", 0), ("RIGHT_HAND", 0)])
                self.assertGreaterEqual(attempts, 2)
            finally:
                adapter.stop()


if __name__ == "__main__":
    unittest.main()
