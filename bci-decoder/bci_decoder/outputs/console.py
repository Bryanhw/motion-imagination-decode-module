"""终端输出：开发阶段最直观的观察窗口。"""

from __future__ import annotations

from ..types import DecoderOutput
from .base import Sink


class ConsoleSink(Sink):
    def __init__(self, every: int = 1) -> None:
        self.every = max(1, int(every))
        self._count = 0

    def emit(self, out: DecoderOutput) -> None:
        self._count += 1
        if self._count % self.every:
            return
        probs = " ".join(f"{p:.2f}" for p in out.probs)
        print(
            f"[{out.t_data:9.3f}s] {out.label:<6} "
            f"conf={out.confidence:.2f}  probs=[{probs}]  "
            f"compute={out.compute_ms:.1f}ms  win={out.window_seconds:.1f}s "
            f"state={out.state}"
        )
