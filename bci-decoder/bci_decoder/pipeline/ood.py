"""域内检测（OOD Detector）：判定当前特征是否落在训练分布内。

背景（2026-10-21，2c 缺陷）：CSP 的 log-方差归一化抹掉信号绝对强度，LDA 对分布外样本
武断给出近 0/1 高置信，现有 min_confidence 门限挡不住“单类虚高”（弱信号/纯噪声被武断判为
单侧 right，conf≈1.0）。本模块在在线链路给引擎增加一道“输入可信度”判定：

    is_outside(feat, strength) == True  → 视为 OOD → 引擎降级输出 idle

两条判据（任一命中即 OOD）：
1. 马氏距离（Mahalanobis，主判据）：训练期收集全部合法窗口的 CSP 特征，计算均值 μ 与
   协方差 Σ；在线计算 D²=(x-μ)ᵀΣ⁻¹(x-μ)，超过阈值即 OOD。
   阈值 τ = max(χ²_{d,0.99}, 训练集经验 p99) × score_scale。
   对“结构性异常”敏感（纯噪声 / 同相波形 / 增益漂移 / 异常通道布局）。
2. 信号强度下限（strength floor，辅助判据）：CSP 归一化会抹掉绝对功率，弱信号 / 近零输入
   / 设备未接好在归一化特征空间未必离群，故用带内强度直接兜底：强度低于训练期 p5 → OOD。
   是 catch 弱信号（如 demo_weak）的关键之一。

设计约束（红线）：
- 默认关闭（enabled=False），灰度开启，不触碰冻结的 9 字段接口契约；
- 训练/在线同口径；使用合成数据仅为工程自检，不对外报告任何准确率；
- save/load 用 joblib，随模型产物发布（artifacts/ 不入库，纪律不变）。
"""

from __future__ import annotations

import numpy as np
from scipy import stats


class OODDetector:
    """训练分布域内检测器（马氏距离为主 + 可选信号强度下限）。

    Attributes:
        method: "mahalanobis" | "none"（none 时全部按域内处理）
        chi2_quantile: 卡方分位，配合特征维数产生理论阈值参考
        score_scale: 阈值整体调节系数（灰调试区间建议 0.8–1.2）
        strength_floor_enabled: 是否启用信号强度下限判据
    """

    def __init__(
        self,
        method: str = "mahalanobis",
        chi2_quantile: float = 0.99,
        score_scale: float = 1.0,
        strength_floor_enabled: bool = False,
    ) -> None:
        self.method = method
        self.chi2_quantile = float(chi2_quantile)
        self.score_scale = float(score_scale)
        self.strength_floor_enabled = bool(strength_floor_enabled)

        self.mu_: np.ndarray | None = None  # (d,)
        self.cov_inv_: np.ndarray | None = None  # (d, d)
        self.tau_chi2_: float | None = None
        self.tau_emp_: float | None = None
        self.strength_floor_: float | None = None

    # ---- 训练期 ----
    def fit(self, feats: np.ndarray, strength: np.ndarray | None = None) -> "OODDetector":
        """用训练期特征（与在线完全同口径）标定域分布。

        Args:
            feats: (n, d) 训练特征矩阵（CSP 输出）。
            strength: (n,) 与 feats 同批次窗口的强度标量（与在线 `strength_fn` 同口径），
                仅当 strength_floor_enabled=True 时必需。
        """
        feats = np.asarray(feats, dtype=np.float64)
        if feats.ndim != 2 or feats.shape[0] < 3:
            raise ValueError(f"训练特征需至少 3 个样本的二维数组，实际 {feats.shape}")

        d = feats.shape[1]
        self.mu_ = feats.mean(axis=0)
        cov = np.cov(feats, rowvar=False)
        eigvals = np.linalg.eigvalsh(cov)
        floor = max(eigvals.max() * 1e-6, 1e-9)  # 数值稳定：保证可逆
        self.cov_inv_ = np.linalg.inv(cov + floor * np.eye(d))

        d2 = self._mahalanobis_dist2(feats)
        self.tau_emp_ = float(np.quantile(d2, 0.99))
        self.tau_chi2_ = float(stats.chi2.ppf(self.chi2_quantile, df=d))

        if self.strength_floor_enabled:
            if strength is None:
                raise ValueError("strength_floor_enabled=True 时必须提供 strength 数组")
            s = np.asarray(strength, dtype=np.float64).reshape(-1)
            if s.size != feats.shape[0]:
                raise ValueError("strength 数组长度必须与特征样本数一致")
            self.strength_floor_ = float(np.quantile(s, 0.05))
        else:
            self.strength_floor_ = None
        return self

    # ---- 在线 ----
    @property
    def fitted(self) -> bool:
        return self.mu_ is not None and self.cov_inv_ is not None

    def _mahalanobis_dist2(self, x: np.ndarray) -> np.ndarray:
        if not self.fitted:
            raise RuntimeError("OODDetector 尚未 fit")
        x = np.asarray(x, dtype=np.float64)
        delta = x - self.mu_
        y = delta @ self.cov_inv_
        return np.einsum("...i,...i->...", y, delta)

    def outside_score(self, feat: np.ndarray) -> bool:
        """仅按马氏距离判断是否域外（不含强度判据）。"""
        if not self.fitted or self.method == "none":
            return False
        if self.tau_chi2_ is None or self.tau_emp_ is None:
            return False
        d2 = float(self._mahalanobis_dist2(np.asarray(feat).reshape(1, -1))[0])
        tau = max(self.tau_chi2_, self.tau_emp_) * self.score_scale
        return d2 > tau

    def strength_outside(self, strength: float) -> bool:
        """仅按强度下限判断是否弱信号/近零输入。"""
        if not self.strength_floor_enabled or self.strength_floor_ is None:
            return False
        return float(strength) < self.strength_floor_

    def is_outside(self, feat: np.ndarray, strength: float | None = None) -> bool:
        """任一判据命中即视为 OOD。strength 为 None 时仅用马氏判据。"""
        if not self.fitted:
            return False
        if self.outside_score(feat):
            return True
        if strength is not None and self.strength_outside(strength):
            return True
        return False

    # ---- 阈值释义（供诊断） ----
    def describe(self) -> dict:
        return {
            "method": self.method,
            "n_features": 0 if self.mu_ is None else int(self.mu_.size),
            "tau_chi2": self.tau_chi2_,
            "tau_emp_p99": self.tau_emp_,
            "tau_final": None if self.tau_chi2_ is None else max(self.tau_chi2_, self.tau_emp_) * self.score_scale,
            "strength_floor": self.strength_floor_,
            "strength_floor_enabled": self.strength_floor_enabled,
        }

    # ---- 持久化 ----
    def save(self, path: str) -> None:
        import os

        import joblib

        if os.path.dirname(path):
            os.makedirs(os.path.dirname(path), exist_ok=True)
        joblib.dump(
            {
                "method": self.method,
                "chi2_quantile": self.chi2_quantile,
                "score_scale": self.score_scale,
                "strength_floor_enabled": self.strength_floor_enabled,
                "mu": self.mu_,
                "cov_inv": self.cov_inv_,
                "tau_chi2": self.tau_chi2_,
                "tau_emp": self.tau_emp_,
                "strength_floor": self.strength_floor_,
            },
            path,
        )

    @classmethod
    def load(cls, path: str) -> "OODDetector":
        import joblib

        d = joblib.load(path)
        obj = cls(
            method=d.get("method", "mahalanobis"),
            chi2_quantile=d.get("chi2_quantile", 0.99),
            score_scale=d.get("score_scale", 1.0),
            strength_floor_enabled=d.get("strength_floor_enabled", False),
        )
        obj.mu_ = d["mu"]
        obj.cov_inv_ = d["cov_inv"]
        obj.tau_chi2_ = d.get("tau_chi2")
        obj.tau_emp_ = d.get("tau_emp")
        obj.strength_floor_ = d.get("strength_floor")
        return obj
