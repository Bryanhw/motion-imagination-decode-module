"""JSONL 落盘：每一行是一条决策记录。

这批数据是后续做"在线自适应/跨被试迁移"的资产，务必在真实测试时开启。
"""

from __future__ import annotations

import json
import os

from ..types import DecoderOutput
from .base import Sink


class JsonlSink(Sink):
    def __init__(self, path: str) -> None:
        self.path = path
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        self._fh = open(self.path, "a", encoding="utf-8")

    def emit(self, out: DecoderOutput) -> None:
        self._fh.write(json.dumps(out.to_dict(), ensure_ascii=False) + "\n")
        self._fh.flush()

    def close(self) -> None:
        try:
            self._fh.close()
        except Exception:
            pass
