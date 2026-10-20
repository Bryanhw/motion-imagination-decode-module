"""端到端测试：mock 源 → 引擎 → 输出，验证整条在线链路能跑通。"""

import numpy as np

from bci_decoder.config import DEFAULT_CH_NAMES, Config
from bci_decoder.core import DecoderEngine
from bci_decoder.pipeline.classifier import LDAClassifier
from bci_decoder.pipeline.features import CSPExtractor
from bci_decoder.pipeline.preprocess import Preprocessor
from bci_decoder.sources import build_source
from bci_decoder.synth import synthesize_dataset


def _cfg():
    cfg = Config()
    cfg.source.kind = "mock"
    cfg.source.realtime = False
    cfg.source.chunk_samples = 25
    cfg.window.window_seconds = 1.0
    cfg.window.step_seconds = 0.25
    return cfg


def test_engine_produces_outputs():
    cfg = _cfg()
    engine = DecoderEngine(cfg)
    src = build_source(cfg.source)
    outputs = []
    for i, chunk in enumerate(src.stream()):
        outputs.extend(engine.push(chunk))
        if i >= 60:
            break
    assert len(outputs) > 0
    out = outputs[-1]
    assert out.label in cfg.classifier.classes + [cfg.postprocess.idle_label]
    assert len(out.probs) == len(cfg.classifier.classes)
    assert 0.0 <= out.confidence <= 1.0
    assert out.compute_ms >= 0.0


def test_mock_signal_carries_class_information():
    """自检：mock 数据本身应当可分（验证流水线有效，而非评估算法）。"""
    from bci_decoder.pipeline.features import BandPowerExtractor

    cfg = _cfg()
    src = build_source(cfg.source)
    ex = BandPowerExtractor(cfg.source.sfreq, cfg.features.bands)
    chunk = next(src.stream())
    for _ in range(40):
        chunk = next(src.stream())
    f = ex.transform(chunk.data)
    assert np.all(np.isfinite(f))


def _train_csp_lda(cfg, tmp_path):
    """训练 CSP+LDA（合成自检数据），落盘两个模型文件，返回 (csp_path, clf_path)。"""
    trials, labels = synthesize_dataset(
        n_per_class=20, ch_names=DEFAULT_CH_NAMES,
        sfreq=cfg.source.sfreq, seconds=2.0, seed=0,
    )
    pre = Preprocessor(cfg.preprocess, len(DEFAULT_CH_NAMES), cfg.source.sfreq)
    cleaned = [pre.process(t)[0] for t in trials]
    csp = CSPExtractor(n_components=4).fit(np.stack(cleaned), labels)
    feats = np.stack([csp.transform(c) for c in cleaned])
    clf = LDAClassifier().fit(feats, labels)
    csp_path = tmp_path / "csp.joblib"
    clf_path = tmp_path / "lda.joblib"
    csp.save(str(csp_path))
    clf.save(str(clf_path))
    return str(csp_path), str(clf_path)


def test_engine_with_csp_feature_config(tmp_path):
    """CSP 路线端到端：训练 → 配置文件指向模型 → mock 流驱动引擎产出输出。"""
    cfg = _cfg()
    csp_path, clf_path = _train_csp_lda(cfg, tmp_path)
    cfg.features.kind = "csp"
    cfg.features.model_path = csp_path
    cfg.classifier.model_path = clf_path

    engine = DecoderEngine(cfg)
    src = build_source(cfg.source)
    outputs = []
    for i, chunk in enumerate(src.stream()):
        outputs.extend(engine.push(chunk))
        if i >= 60:
            break
    assert len(outputs) > 0
    out = outputs[-1]
    assert out.label in cfg.classifier.classes + [cfg.postprocess.idle_label]
    assert len(out.probs) == len(cfg.classifier.classes)
    assert 0.0 <= out.confidence <= 1.0
    assert out.compute_ms >= 0.0
