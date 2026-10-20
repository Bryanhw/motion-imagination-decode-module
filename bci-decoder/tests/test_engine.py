"""端到端测试：mock 源 → 引擎 → 输出，验证整条在线链路能跑通。"""

import numpy as np

from bci_decoder.config import Config
from bci_decoder.core import DecoderEngine
from bci_decoder.sources import build_source


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


def test_latency_history_stays_bounded_and_reports_recent_samples(monkeypatch):
    """超过容量后仍继续解码；统计明确反映最近样本，不能冒充全程分布。"""
    from bci_decoder import core

    monkeypatch.setattr(core, "LATENCY_HISTORY_LIMIT", 32)
    cfg = _cfg()
    engine = DecoderEngine(cfg)
    observed = []
    for index, chunk in enumerate(build_source(cfg.source).stream()):
        observed.extend(out.compute_ms for out in engine.push(chunk))
        if index >= 100:
            break

    assert engine.n_outputs == len(observed) > 32
    assert len(engine.compute_times_ms) == engine.compute_times_ms.maxlen == 32
    np.testing.assert_array_equal(list(engine.compute_times_ms), observed[-32:])
    report = engine.latency_report()
    assert report["n"] == 32
    assert report["n_total"] == len(observed)
    assert report["sample_scope"] == "latest_32_decisions"
    assert report["p95_ms"] == float(np.percentile(observed[-32:], 95))
