"""离线数据回放源：把历史数据当成"实时流"喂给解码引擎。

这是最关键的验证手段——**伪在线测试**：
用真实离线数据分块重放，可以完整检验滤波状态、缓冲、滑窗、延迟，
而不需要占用设备和被试时间。

数据格式：.npy，形状 (n_channels, n_samples)，单位 µV。
"""

from __future__ import annotations

import os
import time
from typing import Iterator, Sequence

import numpy as np

from ..types import EEGChunk
from .base import Source


class ReplaySource(Source):
    def __init__(
        self,
        path: str,
        sfreq: float = 250.0,
        ch_names: Sequence[str] = (),
        chunk_samples: int = 25,
        speed: float = 1.0,
        loop: bool = False,
        realtime: bool = True,
    ):
        if not path or not os.path.exists(path):
            raise FileNotFoundError(f"回放数据不存在: {path!r}")
        self.path = path
        self.sfreq = float(sfreq)
        self.chunk_samples = int(chunk_samples)
        self.speed = max(1e-6, float(speed))
        self.loop = bool(loop)
        self.realtime = bool(realtime)

        data = np.load(path)
        if data.ndim != 2:
            raise ValueError(f"回放数据必须是二维 (n_channels, n_samples)，实际 {data.shape}")
        self.data = data.astype(np.float64)
        self.ch_names = list(ch_names) or [f"ch{i}" for i in range(self.data.shape[0])]
        if len(self.ch_names) != self.data.shape[0]:
            raise ValueError(
                f"通道名数量({len(self.ch_names)})与数据通道数({self.data.shape[0]})不一致"
            )

    @property
    def n_channels(self) -> int:
        return int(self.data.shape[0])

    @property
    def n_samples(self) -> int:
        return int(self.data.shape[1])

    def stream(self) -> Iterator[EEGChunk]:
        while True:
            for start in range(0, self.n_samples, self.chunk_samples):
                block = self.data[:, start:start + self.chunk_samples]
                if block.shape[1] == 0:
                    continue
                chunk = EEGChunk(
                    data=block,
                    sfreq=self.sfreq,
                    t0=start / self.sfreq,
                    ch_names=self.ch_names,
                )
                yield chunk
                if self.realtime:
                    time.sleep(block.shape[1] / self.sfreq / self.speed)
            if not self.loop:
                return
