"""WebSocket 输出：游戏客户端的正式对接方式。

消息格式（每帧一条 JSON）：
    {"t_data": 12.345, "label": "left", "label_id": 0,
     "confidence": 0.83, "probs": [0.83, 0.17],
     "state": "running", "compute_ms": 1.2, "window_seconds": 2.0}

游戏侧无需了解任何脑电细节，只订阅这个端口即可。
"""

from __future__ import annotations

import asyncio
import json
import threading

from ..types import DecoderOutput
from .base import Sink


class WebSocketSink(Sink):
    def __init__(self, host: str = "127.0.0.1", port: int = 8765) -> None:
        try:
            import websockets  # noqa: F401
        except ImportError as e:
            raise RuntimeError("未安装 websockets：pip install websockets") from e

        self.host = host
        self.port = port
        self._clients: set = set()
        self._loop = asyncio.new_event_loop()
        self._ready = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        self._ready.wait(timeout=5.0)

    # ---- 服务器线程 ----
    def _run(self) -> None:
        asyncio.set_event_loop(self._loop)
        try:
            self._loop.run_until_complete(self._serve())
        except Exception:
            pass

    async def _serve(self) -> None:
        import websockets

        async with websockets.serve(self._handler, self.host, self.port):
            self._ready.set()
            await asyncio.Future()   # 永久运行

    async def _handler(self, websocket) -> None:
        self._clients.add(websocket)
        try:
            async with websocket:
                await websocket.wait_closed()
        finally:
            self._clients.discard(websocket)

    # ---- 对外接口 ----
    def emit(self, out: DecoderOutput) -> None:
        if not self._clients:
            return
        payload = json.dumps(out.to_dict(), ensure_ascii=False)
        asyncio.run_coroutine_threadsafe(self._broadcast(payload), self._loop)

    async def _broadcast(self, payload: str) -> None:
        if not self._clients:
            return
        await asyncio.gather(
            *(c.send(payload) for c in list(self._clients)),
            return_exceptions=True,
        )

    def close(self) -> None:
        try:
            self._loop.call_soon_threadsafe(self._loop.stop)
        except Exception:
            pass
