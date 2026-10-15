"""环形缓冲区：在线解码的数据中枢。

为什么不用普通 list：实时系统里数据会无限增长，必须用固定容量缓冲，
并在落后时自动覆盖最旧的数据，保证内存恒定、延迟可控。
"""

from __future__ import annotations

import numpy as np


class RingBuffer:
    """固定容量的多通道环形缓冲。"""

    def __init__(self, n_channels: int, capacity: int, sfreq: float = 250.0):
        self.n_channels = int(n_channels)
        self.capacity = int(capacity)
        self.sfreq = float(sfreq)
        self._buf = np.zeros((self.n_channels, self.capacity), dtype=np.float64)
        self._total = 0          # 历史累计写入样本数（单调递增，不因覆盖而回退）
        self._start_t = None     # 第 0 个样本的时间戳

    # ---- 只读属性 ----
    @property
    def total(self) -> int:
        """历史累计写入的样本总数。"""
        return self._total

    @property
    def filled(self) -> int:
        """当前有效样本数（上限为容量）。"""
        return min(self._total, self.capacity)

    # ---- 写入 ----
    def append(self, data: np.ndarray, t0: float | None = None) -> None:
        data = np.asarray(data, dtype=np.float64)
        if data.ndim == 1:
            data = data[None, :]
        if data.shape[0] != self.n_channels:
            raise ValueError(
                f"通道数不匹配：缓冲区为 {self.n_channels}，输入为 {data.shape[0]}"
            )
        if t0 is not None and self._start_t is None:
            self._start_t = float(t0)

        n_in = data.shape[1]
        pos = 0
        while pos < n_in:
            nb = min(self.capacity, n_in - pos)
            block = data[:, pos:pos + nb]
            w = self._total % self.capacity
            if w + nb <= self.capacity:
                self._buf[:, w:w + nb] = block
            else:
                first = self.capacity - w
                self._buf[:, w:] = block[:, :first]
                self._buf[:, :nb - first] = block[:, first:]
            self._total += nb
            pos += nb

    # ---- 读取 ----
    def get_last(self, n: int) -> np.ndarray | None:
        """取最近 n 个样本，返回 (n_channels, n) 的副本；数据不足或 n<=0 时返回 None。"""
        if n <= 0 or self._total == 0:
            return None
        n = min(int(n), self.filled)
        start = self._total - n
        idx = np.arange(start, self._total) % self.capacity
        return self._buf[:, idx].copy()

    # ---- 时间 ----
    def time_of_index(self, i: int) -> float:
        if self._start_t is None:
            return float("nan")
        return self._start_t + i / self.sfreq

    def latest_time(self) -> float:
        if self._start_t is None or self._total == 0:
            return float("nan")
        return self._start_t + (self._total - 1) / self.sfreq

    def window_start_time(self, n: int) -> float:
        """最近 n 个样本的起始时间戳。"""
        n = min(int(n), self.filled)
        return self.time_of_index(self._total - n)
