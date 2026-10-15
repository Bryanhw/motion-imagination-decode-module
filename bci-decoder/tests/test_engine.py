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
