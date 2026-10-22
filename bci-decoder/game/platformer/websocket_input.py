"""Reconnectable client for the decoder's frozen WebSocket output contract."""

from __future__ import annotations

import asyncio
import json
import math
import queue
import threading
import time

from .input_layer import Decision

DECODER_FIELDS = {
    "t_data", "t_wall", "label", "label_id", "confidence", "probs",
    "state", "compute_ms", "window_seconds",
}
LABELS = {"left": ("LEFT_HAND", 0), "right": ("RIGHT_HAND", 1), "idle": ("NONE", -1)}


def parse_decoder_output(raw: str, sequence: int) -> Decision:
    """Map one decoder output to the game's v1 input without changing its schema."""
    try:
        payload = json.loads(raw)
    except (TypeError, json.JSONDecodeError) as exc:
        raise ValueError(f"WebSocket 消息不是有效 JSON：{exc}") from exc
    if not isinstance(payload, dict) or set(payload) != DECODER_FIELDS:
        raise ValueError("解码器消息字段与冻结的 9 字段契约不匹配")

    label = payload["label"]
    if not isinstance(label, str) or label not in LABELS:
        raise ValueError(f"解码器输出了未知 label：{label!r}")
    intent, expected_id = LABELS[label]
    label_id = payload["label_id"]
    if isinstance(label_id, bool) or not isinstance(label_id, int) or label_id != expected_id:
        raise ValueError("label 与 label_id 不一致，拒绝驱动游戏")

    t_data = payload["t_data"]
    if isinstance(t_data, bool) or not isinstance(t_data, (int, float)) or not math.isfinite(t_data):
        raise ValueError("t_data 必须是有限数值")
    state = payload["state"]
    if not isinstance(state, str) or state not in {"running", "stabilizing", "error"}:
        raise ValueError(f"解码器输出了未知 state：{payload['state']!r}")
    if state != "running":
        intent = "NONE"

    return Decision(1, sequence, intent, "device", float(t_data))


class WebSocketInputAdapter:
    """Subscribe in a worker thread; expose connection and decision events to pygame."""

    def __init__(self, url: str = "ws://127.0.0.1:8765", reconnect_seconds: float = 0.5):
        if reconnect_seconds <= 0:
            raise ValueError("reconnect_seconds 必须大于 0")
        self.url = url
        self.reconnect_seconds = reconnect_seconds
        self.events: queue.Queue[tuple[str, object | None]] = queue.Queue()
        self._ready = threading.Event()
        self._thread: threading.Thread | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._task: asyncio.Task | None = None
        self._stopping = threading.Event()

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stopping.clear()
        self._thread = threading.Thread(target=self._thread_main, name="decoder-ws-client", daemon=True)
        self._thread.start()
        if not self._ready.wait(3):
            raise RuntimeError("游戏 WebSocket 客户端启动超时")

    def _thread_main(self) -> None:
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        self._task = self._loop.create_task(self._consume())
        self._ready.set()
        try:
            self._loop.run_until_complete(self._task)
        except asyncio.CancelledError:
            pass
        finally:
            pending = asyncio.all_tasks(self._loop)
            for task in pending:
                task.cancel()
            if pending:
                self._loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
            self._loop.close()

    async def _consume(self) -> None:
        try:
            import websockets
        except ImportError as exc:
            self.events.put(("connection_error", f"缺少 websockets 依赖：{exc}"))
            return

        sequence = 0
        while not self._stopping.is_set():
            self.events.put(("connecting", None))
            connected = False
            try:
                # websockets 15+ may auto-discover a system proxy; bypass it for
                # the local decoder endpoint so 127.0.0.1 isn't sent to a proxy.
                async with websockets.connect(
                    self.url, open_timeout=2, close_timeout=1, proxy=None,
                ) as websocket:
                    connected = True
                    sequence = 0
                    self.events.put(("connected", None))
                    async for raw in websocket:
                        try:
                            decision = parse_decoder_output(raw, sequence)
                        except ValueError as exc:
                            self.events.put(("invalid", str(exc)))
                            continue
                        sequence += 1
                        self.events.put(("decision", decision))
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                self.events.put(("connection_error", str(exc)))
            finally:
                if connected:
                    self.events.put(("disconnected", None))
            if not self._stopping.is_set():
                await asyncio.sleep(self.reconnect_seconds)

    def poll(self) -> list[tuple[str, object | None]]:
        events = []
        while True:
            try:
                events.append(self.events.get_nowait())
            except queue.Empty:
                return events

    def stop(self) -> None:
        self._stopping.set()
        if self._loop and self._task and not self._task.done():
            self._loop.call_soon_threadsafe(self._task.cancel)
        if self._thread:
            self._thread.join(timeout=3)
