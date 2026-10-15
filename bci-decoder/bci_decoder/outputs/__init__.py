"""输出通道（Sink）：解码结果可以同时送到多个地方。

- console：终端查看，调试用
- jsonl：落盘记录，形成数据资产
- websocket：供游戏客户端实时订阅（正式对接方式）
"""

from __future__ import annotations

from ..config import OutputConfig
from .base import Sink


def build_sinks(cfg: OutputConfig) -> list[Sink]:
    sinks: list[Sink] = []
    for name in cfg.sinks:
        if name == "console":
            from .console import ConsoleSink

            sinks.append(ConsoleSink())
        elif name == "jsonl":
            from .jsonl import JsonlSink

            sinks.append(JsonlSink(cfg.record_path or "decoder_output.jsonl"))
        elif name == "websocket":
            from .websocket import WebSocketSink

            sinks.append(WebSocketSink(host=cfg.ws_host, port=cfg.ws_port))
        else:
            raise ValueError(f"未知的输出通道: {name}")
    return sinks


__all__ = ["Sink", "build_sinks"]
