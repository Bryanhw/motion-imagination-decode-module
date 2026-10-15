"""模块内流转的核心数据结构。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Sequence

import numpy as np


@dataclass
class EEGChunk:
    """一小段脑电数据。

    Attributes:
        data: 形状 (n_channels, n_samples)，单位约定为微伏(µV)。
        sfreq: 采样率 (Hz)。
        t0: 本 chunk 第一个样本的时间戳（秒，来自数据源）。
        ch_names: 通道名，需与 data 的行顺序一致。
    """

    data: np.ndarray
    sfreq: float
    t0: float = 0.0
    ch_names: Sequence[str] = ()

    @property
    def n_channels(self) -> int:
        return int(self.data.shape[0])

    @property
    def n_samples(self) -> int:
        return int(self.data.shape[1])

    def latest_time(self) -> float:
        """本 chunk 最后一个样本的时间戳。"""
        if self.n_samples == 0:
            return float(self.t0)
        return float(self.t0) + (self.n_samples - 1) / float(self.sfreq)


@dataclass
class DecoderOutput:
    """一次解码决策的输出。这是模块对外暴露的唯一"产品"。"""

    t_data: float          # 决策所依据的窗口末端在数据流中的时间戳（秒）
    t_wall: float          # 产生该决策的本地单调时钟时刻（perf_counter）
    label: str             # 解码结果，例如 "left" / "right" / "idle"
    label_id: int          # 类别索引；idle 为 -1
    confidence: float      # 置信度 0~1
    probs: list = field(default_factory=list)   # 各类别概率，顺序同 config.classifier.classes
    state: str = "running"  # running | stabilizing | error
    compute_ms: float = 0.0    # 本次决策的纯计算耗时（不含窗口积累时间）
    window_seconds: float = 0.0  # 窗口长度，构成端到端响应的主要部分

    def to_dict(self) -> dict:
        return {
            "t_data": round(self.t_data, 6),
            "t_wall": round(self.t_wall, 6),
            "label": self.label,
            "label_id": self.label_id,
            "confidence": round(self.confidence, 4),
            "probs": [round(float(p), 4) for p in self.probs],
            "state": self.state,
            "compute_ms": round(self.compute_ms, 3),
            "window_seconds": self.window_seconds,
        }
