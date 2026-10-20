"""在线特征提取。

当前技术路线（2026-10-20 起）：**CSP + log-方差 + LDA**。
- csp：共空间模式，学一组空间滤波矩阵 W 后取 log-方差（当前路线，判别力优于单通道频带功率）。
- bandpower：频带功率对数（旧默认，保留供对照/教学）。
- covariance：协方差矩阵向量化（黎曼几何路线的基础，跨被试更稳，MVP 未启用）。
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


class CSPExtractor:
    """共空间模式（Common Spatial Patterns）特征提取器。

    原理：CSP 是带监督的空间滤波方法，学习一组空间滤波矩阵 W，使得投影后
    一类信号的方差被放大、另一类被压缩（两类方差不平衡最极端的方向）。
    对运动想象（ERD/ERS 体现在 C3/C4 等通道的节律功率差）判别力强于单通道频带功率。

    训练阶段学 W（**有状态**，W 必须随模型一起保存/加载）；在线阶段只调用 transform，
    成本为一次矩阵乘：W @ x → log-方差，无额外计算开销。

    ⚠️ **通道顺序即语义**：W 的行是按通道顺序训练的。本项目通道顺序固定为
    `C3, Cz, C4, CP3, CP4, P3, P4, Oz`，加载已训练 CSP 时必须保证输入窗口通道顺序一致，
    绝对不得重排，否则空间滤波结果会完全错乱。
    """

    def __init__(self, n_components: int = 4, reg: float = 1e-4):
        """n_components: 空间滤波器个数（通常取偶数 2m，即 m 对）。"""
        self.n_components = int(n_components)
        self.reg = float(reg)
        self.filters_: np.ndarray | None = None  # (n_components, n_channels)

    @property
    def trained(self) -> bool:
        return self.filters_ is not None

    @property
    def n_features(self) -> int | None:
        return None if self.filters_ is None else self.n_components

    @staticmethod
    def _mean_cov(windows: np.ndarray, reg: float) -> np.ndarray:
        """窗口集 (n, ch, t) 的平均协方差矩阵 + 收缩正则。"""
        x = np.asarray(windows, dtype=np.float64)
        n, ch, _ = x.shape
        x = x - x.mean(axis=2, keepdims=True)
        denom = max(x.shape[2] - 1, 1)
        covs = [xw @ xw.T / denom for xw in x]
        cov = np.mean(covs, axis=0)
        tr = np.trace(cov) / ch
        return (1.0 - reg) * cov + reg * tr * np.eye(ch)

    def fit(self, x: np.ndarray, y: np.ndarray) -> "CSPExtractor":
        """用带标签的窗口学习空间滤波矩阵 W。

        Args:
            x: (n_windows, n_channels, n_samples)
            y: (n_windows,) 标签，取值 {class0, class1}（二分类经典 CSP）
        """
        from scipy.linalg import eigh

        x = np.asarray(x, dtype=np.float64)
        y = np.asarray(y)
        classes = np.unique(y)
        if classes.size != 2:
            raise ValueError(f"CSP 需要二分类标签，实际类别数: {classes.size}")
        c0 = self._mean_cov(x[y == classes[0]], self.reg)
        c1 = self._mean_cov(x[y == classes[1]], self.reg)

        # 广义特征值问题 c0 w = λ c1 w：λ 大 → 类 0 方差异于类 1 最极端的空间方向
        eigvals, eigvecs = eigh(c0, c1)
        order = np.argsort(eigvals)
        m = self.n_components // 2
        # 取特征值最大 m 个（类0优势）与最小 m 个（类1优势）构成空间滤波器组
        sel = np.concatenate([order[:m], order[-m:]])
        self.filters_ = eigvecs[:, sel].T  # (n_components, n_channels)
        return self

    def transform(self, x: np.ndarray) -> np.ndarray:
        """单窗口 (n_channels, n_samples) → (n_components,)：空间滤波 + log-方差。"""
        if self.filters_ is None:
            raise RuntimeError(
                "CSP 尚未训练：请先运行 scripts/bootstrap_demo.py 训练，"
                "并在配置 features.model_path 指向训练好的 CSP 模型。"
            )
        x = np.asarray(x, dtype=np.float64)
        z = self.filters_ @ x                       # (n_components, n_samples)
        var = np.var(z, axis=1)
        var = np.maximum(var, 1e-12)
        return np.log(var / var.sum())              # 归一化 log-方差特征

    def save(self, path: str) -> None:
        import joblib

        joblib.dump(
            {
                "filters_": self.filters_,
                "n_components": self.n_components,
                "reg": self.reg,
            },
            path,
        )

    @classmethod
    def load(cls, path: str) -> "CSPExtractor":
        import joblib

        d = joblib.load(path)
        obj = cls(n_components=d["n_components"], reg=d["reg"])
        obj.filters_ = d["filters_"]
        return obj


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
    if cfg.kind == "csp":
        if cfg.model_path:
            return CSPExtractor.load(cfg.model_path)
        # 未提供模型：返回可训练的 CSP（在线 transform 会提示先训练）
        return CSPExtractor(n_components=cfg.csp_components, reg=cfg.csp_reg)
    raise ValueError(f"未知的特征类型: {cfg.kind}")
