"""流水线单元测试：滤波器状态连续性、特征维度、分类器接口。"""

import numpy as np
import pytest

from bci_decoder.config import DEFAULT_CH_NAMES, PostprocessConfig, PreprocessConfig
from bci_decoder.pipeline.classifier import LDAClassifier, UntrainedClassifier
from bci_decoder.pipeline.features import BandPowerExtractor, CovarianceExtractor, CSPExtractor
from bci_decoder.pipeline.postprocess import DecisionStabilizer
from bci_decoder.pipeline.preprocess import Preprocessor
from bci_decoder.synth import synthesize_dataset


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


def test_csp_fit_dimension_and_class_separability():
    """CSP：fit 后 transform 输出 (n_components,) 且两类特征在至少一维可分（工程自检，非性能评估）。"""
    trials, labels = synthesize_dataset(
        n_per_class=20, ch_names=DEFAULT_CH_NAMES, seconds=2.0, sfreq=250.0, seed=0
    )
    ex = CSPExtractor(n_components=4).fit(np.stack(trials), labels)
    assert ex.trained
    assert ex.filters_.shape == (4, len(DEFAULT_CH_NAMES))  # (n_components, 8 通道)
    f0 = ex.transform(trials[0])
    assert f0.shape == (4,)
    assert np.all(np.isfinite(f0))
    # 通道顺序敏感：W 的行序与训练通道顺序绑定，特征应体现两类差异（自检口径）
    feats = np.stack([ex.transform(t) for t in trials])
    m0 = feats[labels == 0].mean(axis=0)
    m1 = feats[labels == 1].mean(axis=0)
    assert np.any(np.abs(m0 - m1) > 0.1)


def test_csp_save_load_roundtrip(tmp_path):
    trials, labels = synthesize_dataset(
        n_per_class=15, ch_names=DEFAULT_CH_NAMES, seconds=1.0, sfreq=250.0, seed=1
    )
    ex = CSPExtractor(n_components=4).fit(np.stack(trials), labels)
    p = tmp_path / "csp.joblib"
    ex.save(str(p))
    ex2 = CSPExtractor.load(str(p))
    assert np.allclose(ex.transform(trials[0]), ex2.transform(trials[0]), atol=1e-12)


def test_csp_requires_training_before_transform():
    ex = CSPExtractor(n_components=4)
    with pytest.raises(RuntimeError):
        ex.transform(np.zeros((8, 500)))


def test_csp_rejects_non_binary_labels():
    rng = np.random.default_rng(4)
    x = np.stack([rng.standard_normal((8, 500)) for _ in range(6)])
    y = np.array([0, 0, 0, 1, 1, 2])
    ex = CSPExtractor(n_components=4)
    with pytest.raises(ValueError):
        ex.fit(x, y)


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
