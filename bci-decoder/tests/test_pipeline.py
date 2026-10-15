"""流水线单元测试：滤波器状态连续性、特征维度、分类器接口。"""

import numpy as np

from bci_decoder.config import PreprocessConfig
from bci_decoder.pipeline.classifier import LDAClassifier, UntrainedClassifier
from bci_decoder.pipeline.features import BandPowerExtractor, CovarianceExtractor
from bci_decoder.pipeline.postprocess import DecisionStabilizer
from bci_decoder.config import PostprocessConfig
from bci_decoder.pipeline.preprocess import Preprocessor


def test_preprocessor_shape_and_streaming_state():
    cfg = PreprocessConfig()
    pre = Preprocessor(cfg, n_channels=3, sfreq=250.0)
    x = np.random.default_rng(0).standard_normal((3, 25))
    y1, clean1 = pre.process(x)
    y2, clean2 = pre.process(x)
    assert y1.shape == (3, 25)
    assert y2.shape == (3, 25)
    assert isinstance(clean1, bool)
    # 因果滤波：分段处理与整段处理的连续结果应当一致（状态被正确保持）
    pre2 = Preprocessor(cfg, n_channels=3, sfreq=250.0)
    whole, _ = pre2.process(np.concatenate([x, x], axis=1))
    assert np.allclose(np.concatenate([y1, y2], axis=1), whole, atol=1e-8)


def test_bandpower_feature_dimension():
    ex = BandPowerExtractor(250.0, {"mu": [8, 13], "beta": [13, 30]})
    x = np.random.default_rng(1).standard_normal((4, 500))
    f = ex.transform(x)
    assert f.shape == (8,)   # 4 通道 × 2 频带


def test_covariance_feature_dimension():
    ex = CovarianceExtractor(250.0)
    x = np.random.default_rng(2).standard_normal((4, 500))
    f = ex.transform(x)
    assert f.shape == (10,)  # 上三角 4*5/2


def test_lda_train_and_predict_proba():
    rng = np.random.default_rng(3)
    x = np.vstack([rng.normal(0, 1, (30, 8)), rng.normal(3, 1, (30, 8))])
    y = np.array([0] * 30 + [1] * 30)
    clf = LDAClassifier().fit(x, y)
    p = clf.predict_proba(x[0])
    assert p.shape == (2,)
    assert abs(p.sum() - 1.0) < 1e-6


def test_untrained_classifier_is_uniform():
    p = UntrainedClassifier(2).predict_proba(np.zeros(8))
    assert np.allclose(p, [0.5, 0.5])


def test_stabilizer_requires_consistency():
    cfg = PostprocessConfig(vote_window=3, ema_alpha=1.0, min_confidence=0.6)
    st = DecisionStabilizer(cfg)
    names = ["left", "right"]
    # 前两次只投票，尚未形成连续一致 → 保持 idle
    assert st.update(np.array([0.9, 0.1]), names)[0] == "idle"
    assert st.update(np.array([0.9, 0.1]), names)[0] == "idle"
    # 第三次连续一致且置信度足够 → 输出 left
    assert st.update(np.array([0.9, 0.1]), names)[0] == "left"
    # 抖动时保持上一次输出，而不是反复切换
    st.update(np.array([0.1, 0.9]), names)
    assert st.update(np.array([0.9, 0.1]), names)[0] == "left"


def test_stabilizer_low_confidence_gives_idle():
    cfg = PostprocessConfig(vote_window=2, ema_alpha=1.0, min_confidence=0.9, idle_label="idle")
    st = DecisionStabilizer(cfg)
    names = ["left", "right"]
    st.update(np.array([0.6, 0.4]), names)
    assert st.update(np.array([0.6, 0.4]), names)[0] == "idle"
