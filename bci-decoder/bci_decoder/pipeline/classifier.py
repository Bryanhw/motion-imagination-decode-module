"""分类器。

统一接口：fit / predict_proba / save / load。
在线推理只调用 predict_proba，因此换成深度模型（ONNX）时无需改动引擎。
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional

import numpy as np

from ..config import ClassifierConfig


class BaseClassifier(ABC):
    @abstractmethod
    def predict_proba(self, x: np.ndarray) -> np.ndarray:
        """输入单样本特征 (n_features,)，返回类别概率 (n_classes,)。"""

    def fit(self, x: np.ndarray, y: np.ndarray) -> "BaseClassifier":
        raise NotImplementedError

    def save(self, path: str) -> None:
        raise NotImplementedError


class LDAClassifier(BaseClassifier):
    """标准化 + 线性判别分析。小数据、低延迟场景的强基线。"""

    def __init__(self) -> None:
        from sklearn.discriminant_analysis import LinearDiscriminantAnalysis
        from sklearn.pipeline import Pipeline
        from sklearn.preprocessing import StandardScaler

        self.pipe = Pipeline([
            ("scaler", StandardScaler()),
            ("lda", LinearDiscriminantAnalysis()),
        ])

    def fit(self, x: np.ndarray, y: np.ndarray) -> "LDAClassifier":
        self.pipe.fit(np.atleast_2d(x), np.asarray(y))
        return self

    def predict_proba(self, x: np.ndarray) -> np.ndarray:
        return self.pipe.predict_proba(np.atleast_2d(x))[0]

    def save(self, path: str) -> None:
        import joblib

        joblib.dump(self.pipe, path)

    @classmethod
    def load(cls, path: str) -> "LDAClassifier":
        import joblib

        obj = cls.__new__(cls)
        obj.pipe = joblib.load(path)
        return obj


class UntrainedClassifier(BaseClassifier):
    """占位分类器：输出均匀概率。

    作用：让整条在线链路（缓冲→滤波→特征→输出）在模型尚未训练时也能跑通，
    便于先验证工程链路，再替换成真实模型。
    """

    def __init__(self, n_classes: int = 2) -> None:
        self.n_classes = int(n_classes)

    def predict_proba(self, x: np.ndarray) -> np.ndarray:
        return np.ones(self.n_classes) / self.n_classes


class OnnxClassifier(BaseClassifier):
    """ONNX 推理占位（用于把训练好的深度模型部署到低延迟环境）。"""

    def __init__(self, path: str, n_classes: int = 2) -> None:
        try:
            import onnxruntime as ort  # noqa: F401
        except ImportError as e:  # pragma: no cover
            raise RuntimeError("未安装 onnxruntime：pip install onnxruntime") from e
        import onnxruntime as ort

        self.session = ort.InferenceSession(path, providers=["CPUExecutionProvider"])
        self.input_name = self.session.get_inputs()[0].name
        self.n_classes = n_classes

    def predict_proba(self, x: np.ndarray) -> np.ndarray:
        out = self.session.run(
            None, {self.input_name: np.atleast_2d(x).astype(np.float32)}
        )[0]
        p = np.asarray(out).ravel()
        p = np.exp(p - p.max())
        return p / p.sum()


def build_classifier(cfg: ClassifierConfig) -> BaseClassifier:
    n_classes = len(cfg.classes)
    if cfg.kind == "lda":
        if cfg.model_path:
            return LDAClassifier.load(cfg.model_path)
        return UntrainedClassifier(n_classes)
    if cfg.kind == "onnx":
        return OnnxClassifier(cfg.onnx_path, n_classes)
    if cfg.kind == "untrained":
        return UntrainedClassifier(n_classes)
    raise ValueError(f"未知的分类器类型: {cfg.kind}")
