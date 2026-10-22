"""合成脑电源：无需任何硬件/数据即可跑通整条链路。

原理：交替生成两类"想象"状态——
- 类别 0（想象左手）：C3 附近 alpha(10Hz) 功率增强
- 类别 1（想象右手）：C4 附近 alpha(10Hz) 功率增强
这正是运动想象最典型的 ERD/ERS 现象，因此用 bandpower 特征可以被区分，
可用于验证整条流水线是否工作正常（属于"自检"，不是算法性能评估）。
"""

from __future__ import annotations

import time
from typing import Iterator, Sequence

import numpy as np

from ..types import EEGChunk
from .base import Source


class MockSource(Source):
    def __init__(
        self,
        sfreq: float = 250.0,
        ch_names: Sequence[str] = ("C3", "Cz", "C4"),
        chunk_samples: int = 25,
        realtime: bool = True,
        seed: int = 0,
        label_period_seconds: float = 4.0,
    ):
        self.sfreq = float(sfreq)
        self.ch_names = list(ch_names)
        self.chunk_samples = int(chunk_samples)
        self.realtime = bool(realtime)
        self._rng = np.random.default_rng(seed)
        self._t = 0
        self._label_period = int(label_period_seconds * self.sfreq)
        self._state = "left"
        # 实时节流：用 perf_counter 截止时刻 + 短步进 sleep 自愈。
        # Windows 长时间 time.sleep 偶发丢失唤醒（尤其系统 S3 睡眠/恢复后）会导致 mock 停摆
        # （A10 soak 两轮复现卡在 t≈2788.5s；快跑/纯 sleep 均正常）。短步进可避免单次 sleep 异常致死。
        self._next_sample_time = 0.0

    @property
    def n_channels(self) -> int:
        return len(self.ch_names)

    def _index_of(self, name: str) -> int | None:
        try:
            return self.ch_names.index(name)
        except ValueError:
            return None

    def stream(self) -> Iterator[EEGChunk]:
        n_ch = self.n_channels
        c3 = self._index_of("C3")
        c4 = self._index_of("C4")

        while True:
            n = self.chunk_samples
            idx = np.arange(self._t, self._t + n)
            label = (idx // self._label_period) % 2          # 每 label_period 秒切换
            t = idx / self.sfreq

            alpha = np.sin(2 * np.pi * 10.0 * t)             # 10Hz 节律
            gain = np.ones((n_ch, n), dtype=np.float64)
            if c3 is not None:
                gain[c3] = 1.0 + 0.8 * (1 - label)           # 左手 → C3 增强
            if c4 is not None:
                gain[c4] = 1.0 + 0.8 * label                 # 右手 → C4 增强

            # 单位 µV：节律约 15µV，背景噪声约 5µV
            data = 15.0 * alpha[None, :] * gain
            data += 5.0 * self._rng.standard_normal((n_ch, n))

            chunk = EEGChunk(
                data=data,
                sfreq=self.sfreq,
                t0=idx[0] / self.sfreq,
                ch_names=self.ch_names,
            )
            self._t += n
            self._state = "left" if label[0] == 0 else "right"

            yield chunk

            if self.realtime:
                self._keep_rate(n)

    def _keep_rate(self, n: int) -> None:
        """按样本数推进实时节流，截止时刻驱动、短步进自愈。

        原实现 time.sleep(n/sfreq) 在 Windows 长时间运行后偶发丢失唤醒
        （尤其系统 S3 睡眠/恢复后），表现为整条链路停摆（A10 soak 两轮复现）。
        改为按 perf_counter 绝对截止时刻分段短睡：即使单次 sleep 过长/丢失，
        下一轮也会基于真实经过时间自动追平，不会累计漂移或永久停摆。
        """
        if self._next_sample_time <= 0.0:
            # 首次：以当前时刻为基准
            self._next_sample_time = time.perf_counter()
        self._next_sample_time += n / self.sfreq
        while True:
            remaining = self._next_sample_time - time.perf_counter()
            if remaining <= 0:
                break
            # 短步进 sleep：单次最长 10ms，避免一次性长 sleep 被系统丢弃
            time.sleep(min(remaining, 0.01))
