"""在线特征提取。

两套特征，对应两种主流技术路线：
- bandpower：频带功率对数（传统、可解释、快）。
- covariance：协方差矩阵向量化（黎曼几何路线的基础，跨被试更稳）。
"""

from __future__ import annotations

import numpy as np
from scipy.signal import welch

from ..config import FeatureConfig


def bandpower(x: np.ndarray, sfreq: float, band: tuple[float, float],
              nperseg: int | None = None) -> np.ndarray:
    """计算多通道在某频带的平均功率，返回 (n_channels,)。"""
    x = np.asarray(x, dtype=np.float64)
    n_t = x.shape[-1]
    if n_t < 4:
        return np.zeros(x.shape[0])
    nperseg = int(nperseg or min(n_t, 256))
    f, pxx = welch(x, fs=sfreq, nperseg=nperseg, axis=-1)
    idx = (f >= band[0]) & (f <= band[1])
    if not np.any(idx):
        return np.zeros(x.shape[0])
    return np.trapezoid(pxx[..., idx], f[idx], axis=-1)


class BandPowerExtractor:
    """对每个频带取对数功率并拼接成特征向量。"""

    def __init__(self, sfreq: float, bands: dict):
        self.sfreq = float(sfreq)
        self.bands = {k: tuple(v) for k, v in bands.items()}

    @property
    def n_features(self) -> int | None:
        return None  # 依赖通道数，运行时才能确定

    def transform(self, x: np.ndarray) -> np.ndarray:
        x = np.asarray(x, dtype=np.float64)
        feats = []
        for _, band in self.bands.items():
            bp = bandpower(x, self.sfreq, band)
            feats.append(np.log(bp + 1e-12))   # 对数压缩，接近高斯分布
        return np.concatenate(feats)


class CovarianceExtractor:
    """协方差矩阵 + 收缩估计，返回上三角向量（含对角线）。"""

    def __init__(self, sfreq: float, shrinkage: float = 0.1):
        self.sfreq = float(sfreq)
        self.shrinkage = float(shrinkage)

    def transform(self, x: np.ndarray) -> np.ndarray:
        x = np.asarray(x, dtype=np.float64)
        n_ch = x.shape[0]
        x = x - x.mean(axis=1, keepdims=True)
        denom = max(x.shape[1] - 1, 1)
        cov = x @ x.T / denom
        tr = np.trace(cov) / n_ch
        cov = (1.0 - self.shrinkage) * cov + self.shrinkage * tr * np.eye(n_ch)
        iu = np.triu_indices(n_ch)
        return cov[iu]


def euclidean_align(x: np.ndarray, r_ref: np.ndarray) -> np.ndarray:
    """欧氏对齐（Euclidean Alignment）。

    把不同被试/不同 session 的协方差分布对齐到同一参考点，
    是提升跨被试性能最简单有效的手段之一。

    Args:
        x: 原始数据 (n_channels, n_samples)
        r_ref: 参考平均协方差矩阵 (n_channels, n_channels)
    """
    from scipy.linalg import sqrtm

    w = np.linalg.inv(sqrtm(r_ref).real)
    return w @ x


def build_feature_extractor(cfg: FeatureConfig, sfreq: float):
    if cfg.kind == "bandpower":
        return BandPowerExtractor(sfreq, cfg.bands)
    if cfg.kind == "covariance":
        return CovarianceExtractor(sfreq, cfg.covariance_shrinkage)
    raise ValueError(f"未知的特征类型: {cfg.kind}")
