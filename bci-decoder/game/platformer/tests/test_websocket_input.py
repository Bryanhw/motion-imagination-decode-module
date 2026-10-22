"""Checks for the decoder-to-game WebSocket message mapping."""

import asyncio
import json
import unittest

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


class WebSocketReconnectTests(unittest.IsolatedAsyncioTestCase):
    async def wait_for_event(self, adapter, wanted, pending):
        deadline = asyncio.get_running_loop().time() + 5
        while asyncio.get_running_loop().time() < deadline:
            pending.extend(adapter.poll())
            for event in pending[:]:
                if event[0] == wanted:
                    pending.remove(event)
                    return event
            await asyncio.sleep(0.01)
        self.fail(f"5 秒内没有收到 WebSocket 事件 {wanted!r}；排队事件={pending!r}")

    async def test_reconnects_after_decoder_server_restart(self):
        import websockets

        async def make_server(label, label_id, port):
            async def handler(websocket):
                await websocket.send(json.dumps(decoder_message(label, label_id)))
                await websocket.wait_closed()

            return await websockets.serve(handler, "127.0.0.1", port)

        first = await make_server("left", 0, 0)
        port = first.sockets[0].getsockname()[1]
        adapter = WebSocketInputAdapter(f"ws://127.0.0.1:{port}", reconnect_seconds=0.05)
        pending = []
        adapter.start()
        second = None
        try:
            await self.wait_for_event(adapter, "connected", pending)
            first_decision = await self.wait_for_event(adapter, "decision", pending)
            self.assertEqual((first_decision[1].intent, first_decision[1].sequence), ("LEFT_HAND", 0))

            first.close()
            await first.wait_closed()
            await self.wait_for_event(adapter, "disconnected", pending)
            second = await make_server("right", 1, port)

            await self.wait_for_event(adapter, "connected", pending)
            second_decision = await self.wait_for_event(adapter, "decision", pending)
            self.assertEqual((second_decision[1].intent, second_decision[1].sequence), ("RIGHT_HAND", 0))
        finally:
            first.close()
            await first.wait_closed()
            if second:
                second.close()
                await second.wait_closed()
            await asyncio.to_thread(adapter.stop)


if __name__ == "__main__":
    unittest.main()
