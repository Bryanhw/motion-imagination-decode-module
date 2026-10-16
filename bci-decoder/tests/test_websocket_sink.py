"""WebSocket 输出通道契约测试。

只验证工程通路（字段契约、关停行为），不评估任何算法性能。
"""

from __future__ import annotations

import asyncio
import json
import socket
import threading
import time

import pytest

websockets = pytest.importorskip("websockets")

from bci_decoder.outputs.websocket import WebSocketSink
from bci_decoder.types import DecoderOutput

FROZEN_FIELDS = {
    "t_data", "t_wall", "label", "label_id", "confidence",
    "probs", "state", "compute_ms", "window_seconds",
}


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


def _make_output(i: int, label: str, label_id: int, confidence: float, probs: list) -> DecoderOutput:
    return DecoderOutput(
        t_data=10.0 + i * 0.5,
        t_wall=time.perf_counter(),
        label=label,
        label_id=label_id,
        confidence=confidence,
        probs=probs,
        state="running",
        compute_ms=1.0 + i,
        window_seconds=2.0,
    )


CASES = [
    ("left", 0, 0.81, [0.81, 0.19]),
    ("right", 1, 0.77, [0.23, 0.77]),
    ("idle", -1, 0.00, [0.50, 0.50]),
]


def _collect(port: int, count: int, connected: threading.Event) -> list:
    async def _run() -> list:
        got = []
        async with websockets.connect(f"ws://127.0.0.1:{port}") as ws:
            connected.set()                        # 已登记连接，主线程可以开始发了
            for _ in range(count):
                raw = await asyncio.wait_for(ws.recv(), timeout=10.0)
                got.append(json.loads(raw))
        return got

    return asyncio.run(_run())


def test_websocket_sink_broadcasts_frozen_contract():
    """广播的每条消息字段 == 冻结契约，且 label_id == -1 当且仅当 label == idle。"""
    port = _free_port()
    sink = WebSocketSink("127.0.0.1", port)

    results = {}
    connected = threading.Event()

    def _client() -> None:
        try:
            results["msgs"] = _collect(port, len(CASES), connected)
        except Exception as e:                      # pragma: no cover - 失败时暴露真实原因
            results["error"] = repr(e)
            connected.set()

    t = threading.Thread(target=_client, daemon=True)
    t.start()
    assert connected.wait(timeout=5.0), "客户端未能在 5s 内连上输出端口"
    try:
        for i, (label, label_id, conf, probs) in enumerate(CASES):
            sink.emit(_make_output(i, label, label_id, conf, probs))
        t.join(timeout=15)
    finally:
        sink.close()

    assert "error" not in results, results.get("error")
    msgs = results.get("msgs", [])
    assert len(msgs) == len(CASES), f"应收到 {len(CASES)} 条，实际 {len(msgs)}"

    for m in msgs:
        assert set(m.keys()) == FROZEN_FIELDS
        assert (m["label_id"] == -1) == (m["label"] == "idle")
        assert len(m["probs"]) == 2
        assert abs(sum(m["probs"]) - 1.0) < 1e-6
        assert m["state"] in ("running", "stabilizing")
        assert isinstance(m["compute_ms"], (int, float))
        assert isinstance(m["window_seconds"], (int, float))


def test_websocket_sink_close_is_idempotent_and_safe_after_close():
    """close() 可重复调用；关闭后 emit 不应抛异常（游戏/CLI 退出路径）。"""
    port = _free_port()
    sink = WebSocketSink("127.0.0.1", port)
    sink.close()
    sink.close()                                    # 幂等
    sink.emit(_make_output(0, "idle", -1, 0.0, [0.5, 0.5]))   # 关停后发送：静默丢弃
