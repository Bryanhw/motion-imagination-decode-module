"""在线预处理。

与离线处理最大的区别：**必须使用因果滤波器并保持跨 chunk 的滤波状态**，
否则每个 chunk 边界都会产生跳变，导致特征抖动、在线表现远差于离线。
"""

from __future__ import annotations

import numpy as np
from scipy.signal import butter, iirnotch, sosfilt, tf2sos

from ..config import PreprocessConfig


class StreamFilter:
    """带状态的因果 IIR 滤波器（SOS 二阶节级联），可跨 chunk 连续处理。"""

    def __init__(self, sos: np.ndarray, n_channels: int):
        self.sos = np.asarray(sos, dtype=np.float64)
        # scipy.sosfilt 在多通道 (n_ch, n_t) + axis=-1 时，zi 形状为 (n_sections, n_ch, 2)
        self.state = np.zeros((self.sos.shape[0], int(n_channels), 2), dtype=np.float64)

    def process(self, x: np.ndarray) -> np.ndarray:
        y, self.state = sosfilt(self.sos, x, axis=-1, zi=self.state)
        return y

    def reset(self) -> None:
        self.state[...] = 0.0


def design_bandpass(sfreq: float, l_freq: float, h_freq: float, order: int = 4) -> np.ndarray:
    return butter(order, [l_freq, h_freq], btype="bandpass", fs=sfreq, output="sos")


def design_notch(sfreq: float, f0: float, q: float = 30.0) -> np.ndarray:
    b, a = iirnotch(f0, q, fs=sfreq)
    return tf2sos(b, a)


class Preprocessor:
    """滤波 + 重参考 + 伪迹标记。"""

    def __init__(self, cfg: PreprocessConfig, n_channels: int, sfreq: float):
        self.cfg = cfg
        self.n_channels = int(n_channels)
        self.sfreq = float(sfreq)

        sos_notch = design_notch(sfreq, cfg.notch_freq, cfg.notch_q)
        nyq = sfreq / 2.0
        h = min(cfg.h_freq, nyq * 0.95)
        l = max(cfg.l_freq, 0.1)
        sos_band = design_bandpass(sfreq, l, h, cfg.filter_order)

        self.notch = StreamFilter(sos_notch, self.n_channels)
        self.band = StreamFilter(sos_band, self.n_channels)
        self.last_clean = True

    def process(self, x: np.ndarray) -> tuple[np.ndarray, bool]:
        """处理一个 chunk，返回 (处理后数据, 是否干净)。"""
        x = np.asarray(x, dtype=np.float64)
        if x.ndim == 1:
            x = x[None, :]

        y = self.notch.process(x)
        y = self.band.process(y)

        if self.cfg.car:
            y = y - y.mean(axis=0, keepdims=True)

        # 伪迹检测：单位假设为 µV，峰峰值过大说明有眨眼/肌电/运动伪迹
        ptp = np.ptp(y, axis=1)
        clean = bool(np.all(ptp < self.cfg.artifact_ptp_uv))
        self.last_clean = clean
        return y, clean

    def reset(self) -> None:
        self.notch.reset()
        self.band.reset()
