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
from typing import Optional

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
        self._error: Optional[BaseException] = None
        self._stop = asyncio.Event()   # 由 close() 唤醒，使 _serve 正常退出
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        # 绑定失败必须**立刻报错**：静默不服务会让游戏端干等到超时，
        # 现场演示时表现为"游戏连不上、日志却没有任何异常"。
        if not self._ready.wait(timeout=5.0):
            raise RuntimeError(f"WebSocket 输出启动超时（{self.host}:{self.port}）")
        if self._error is not None:
            error = self._error
            self.close()
            raise RuntimeError(
                f"WebSocket 输出启动失败（{self.host}:{self.port}）：{error!r}"
            ) from error

    # ---- 服务器线程 ----
    def _run(self) -> None:
        asyncio.set_event_loop(self._loop)
        try:
            self._loop.run_until_complete(self._serve())
        except Exception as e:              # 绑定失败等：交给 __init__ 抛出
            self._error = e
        finally:
            self._ready.set()               # 无论成败都唤醒 __init__，不要干等超时

    async def _serve(self) -> None:
        import websockets

        async with websockets.serve(self._handler, self.host, self.port) as server:
            if self.port == 0:
                # port=0：由操作系统分配，避免"先探测空闲端口再绑定"的竞争
                self.port = int(server.sockets[0].getsockname()[1])
            self._ready.set()
            await self._stop.wait()   # close() 前一直服务

    async def _handler(self, websocket) -> None:
        self._clients.add(websocket)
        try:
            async with websocket:
                await websocket.wait_closed()
        finally:
            self._clients.discard(websocket)

    # ---- 对外接口 ----
    @property
    def client_count(self) -> int:
        """已登记（握手完成且服务端已受理）的客户端数量。

        注意：客户端侧 `websockets.connect()` 返回只代表**握手完成**，服务端
        `_handler` 把它登记进 `_clients` 可能稍晚一步；而 `emit()` 在没有已登记
        客户端时**按设计静默丢弃**（解码器空跑不阻塞）。因此测试与自检脚本若要在
        连接后立刻断言"发出去的消息都被收到"，必须先等本值 > 0，否则会偶发丢首条。
        """
        return len(self._clients)

    def emit(self, out: DecoderOutput) -> None:
        if not self._clients or self._loop.is_closed():
            return
        payload = json.dumps(out.to_dict(), ensure_ascii=False)
        try:
            asyncio.run_coroutine_threadsafe(self._broadcast(payload), self._loop)
        except RuntimeError:
            pass   # 关停竞态：丢弃本次发送，不打断调用方

    async def _broadcast(self, payload: str) -> None:
        if not self._clients:
            return
        await asyncio.gather(
            *(c.send(payload) for c in list(self._clients)),
            return_exceptions=True,
        )

    def close(self) -> None:
        """优雅关停（幂等）：唤醒服务协程 → 等线程收尾 → 关闭事件循环。

        直接 stop() 会让 serve() 的上下文管理器在已关闭的循环上收尾，
        退出时抛出一串 RuntimeError；这里改为正常退出该上下文。
        """
        try:
            self._clients.clear()
            if not self._loop.is_closed():
                self._loop.call_soon_threadsafe(self._stop.set)
        except Exception:
            pass
        try:
            self._thread.join(timeout=3.0)
        except Exception:
            pass
        try:
            if not self._loop.is_closed():
                self._loop.close()
        except Exception:
            pass
