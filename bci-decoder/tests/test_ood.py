"""OOD 域内检测测试（2c 缺陷 · D2 提案落地）。

口径：本批全部使用合成自检数据，仅证明机制有效，不等于算法性能，禁止对外报告。
计数：以 “22 + N_ood” 方式单独统计，不与既有 22 项合并。

覆盖：
- 单元：fit / save / load round-trip；训练域内样本不误杀；结构性噪声（高强度、马氏命中）；
  弱信号/近零输入（强度判据兜底）；method=none 全放行。
- 集成：引擎开启 OOD 后，纯噪声输入被强制 idle（label_id=-1）；域内强信号不被误杀；
  开关关闭时行为与旧版一致（不强制 idle）。
"""

import dataclasses

import numpy as np

from bci_decoder.config import Config
from bci_decoder.core import DecoderEngine
from bci_decoder.pipeline.classifier import LDAClassifier
from bci_decoder.pipeline.features import CSPExtractor
from bci_decoder.pipeline.ood import OODDetector
from bci_decoder.pipeline.preprocess import Preprocessor
from bci_decoder.synth import synthesize_dataset
from bci_decoder.types import EEGChunk


# --------------------------------------------------------------------------- helpers
def _make_domain(tmp_path, n_per_class: int = 20, seed: int = 0):
    """用合成数据（纯自检口径）构建训练域并落盘三种产物，返回 (paths, feats, strengths, ood, csp, trials)。"""

    cfg = Config()
    ch = list(cfg.source.ch_names)
    trials, labels = synthesize_dataset(
        n_per_class=n_per_class, ch_names=ch, sfreq=250.0, seconds=2.0, seed=seed,
    )
    pre = Preprocessor(cfg.preprocess, len(ch), 250.0)
    cleaned = []
    for tr in trials:
        c, _ = pre.process(tr)
        cleaned.append(c)
        pre.reset()
    csp = CSPExtractor(n_components=cfg.features.csp_components, reg=cfg.features.csp_reg)
    csp.fit(np.stack(cleaned), labels)
    feats = np.asarray([csp.transform(c) for c in cleaned])
    strengths = np.asarray([np.sqrt(np.mean(np.var(c, axis=1))) for c in cleaned])
    clf = LDAClassifier().fit(feats, labels)
    ood = OODDetector(method="mahalanobis", strength_floor_enabled=True).fit(feats, strengths)

    paths = {
        "csp": str(tmp_path / "csp.joblib"),
        "lda": str(tmp_path / "lda.joblib"),
        "ood": str(tmp_path / "ood.joblib"),
    }
    csp.save(paths["csp"])
    clf.save(paths["lda"])
    ood.save(paths["ood"])
    return paths, feats, strengths, ood, csp, trials


def _structural_noise_feats(csp, n: int = 60, seed: int = 7, scale: float = 50.0):
    """高强度纯噪声（无 CSP 结构）：强度远高于训练域，只能靠马氏距离判出。"""
    rng = np.random.default_rng(seed)
    feats = []
    for _ in range(n):
        noise = scale * rng.standard_normal((8, 500))
        feats.append(csp.transform(noise))
    return np.asarray(feats)


def _engine_cfg(paths, enabled: bool):
    cfg = Config()
    cfg.features = dataclasses.replace(
        cfg.features, kind="csp", model_path=paths["csp"],
    )
    cfg.classifier = dataclasses.replace(
        cfg.classifier, kind="lda", classes=["left", "right"], model_path=paths["lda"],
    )
    cfg.ood = dataclasses.replace(
        cfg.ood, enabled=enabled, method="mahalanobis",
        strength_floor_enabled=True, model_path=paths["ood"],
    )
    return cfg


# ------------------------------------------------------------------ 单元测试
def test_ood_roundtrip_preserves_domain(tmp_path):
    paths, _feats, strengths, _ood, _csp, _trials = _make_domain(tmp_path)
    loaded = OODDetector.load(paths["ood"])
    assert loaded.fitted
    assert loaded.describe()["method"] == "mahalanobis"
    assert loaded.tau_chi2_ is not None and loaded.tau_emp_ is not None
    # 训练域中位以上强度的样本必须不被强度判据误杀（p5 截断最低 5% 属正常语义）
    med = float(np.median(strengths))
    for s in strengths[strengths >= med]:
        assert loaded.strength_outside(float(s)) is False


def test_ood_inliers_mostly_kept(tmp_path):
    _paths, feats, strengths, ood, _csp, _trials = _make_domain(tmp_path)
    hits = [ood.is_outside(f, float(s)) for f, s in zip(feats, strengths)]
    assert np.mean(hits) < 0.1


def test_ood_structural_noise_is_outside(tmp_path):
    _paths, _feats, _strengths, ood, csp, _trials = _make_domain(tmp_path)
    out = _structural_noise_feats(csp)
    # 高强度噪声强度高于训练域强度判据（不触发 strength），必须由马氏距离判出
    assert ood.strength_outside(1000.0) is False
    hits = [ood.outside_score(f) for f in out]
    assert np.mean(hits) > 0.9


def test_ood_strength_floor_catches_weak_input(tmp_path):
    _paths, feats, strengths, ood, _csp, _trials = _make_domain(tmp_path)
    weak = float(strengths.min()) * 0.05  # 远低于训练域 → 弱信号/近零输入
    assert ood.strength_outside(weak) is True
    # 用域内特征点（马氏不判 OOD）但强度极低 → 强度判据兜住
    assert ood.is_outside(feats[0], weak) is True


def test_ood_method_none_allows_all(tmp_path):
    _paths, feats, strengths, ood, csp, _trials = _make_domain(tmp_path)
    ood.method = "none"
    assert ood.outside_score(_structural_noise_feats(csp)[0]) is False
    assert ood.is_outside(feats[0], float(strengths[0])) is False


# ------------------------------------------------------------------ 集成测试
def test_engine_ood_disabled_no_forced_idle(tmp_path):
    """开关关闭时行为与旧版一致：同输入不被强制 idle（复现 2c 缺陷行为，证明开关确实生效）。"""
    paths, _feats, _strengths, _ood, _csp, _trials = _make_domain(tmp_path)
    cfg = _engine_cfg(paths, enabled=False)
    eng = DecoderEngine(cfg)
    assert eng.ood is None
    rng = np.random.default_rng(11)
    labels_out = []
    for _ in range(240):
        chunk = EEGChunk(data=rng.standard_normal((8, 25)) * 0.5, sfreq=250.0, t0=0.0)
        for o in eng.push(chunk):
            labels_out.append(o.label)
    # 综合自检：旧链路对噪声依 min_confidence 出现非 idle 决策（这正是 2c 缺陷行为）
    assert any(l != "idle" for l in labels_out)


def test_engine_ood_forced_idle_on_noise(tmp_path):
    """开关开启：纯噪声输入（强度低 + 结构异常）被强制 idle，且 label_id 恒为 -1（契约不变）。"""
    paths, _feats, _strengths, _ood, _csp, _trials = _make_domain(tmp_path)
    cfg = _engine_cfg(paths, enabled=True)
    eng = DecoderEngine(cfg)
    assert eng.ood is not None
    rng = np.random.default_rng(11)
    labels_out = []
    for _ in range(240):
        chunk = EEGChunk(data=rng.standard_normal((8, 25)) * 0.5, sfreq=250.0, t0=0.0)
        for o in eng.push(chunk):
            labels_out.append(o.label)
            assert o.label == "idle"
            assert o.label_id == -1
    assert len(labels_out) > 0


def test_engine_ood_missing_model_degrades_gracefully(tmp_path):
    """oo.enabled=True 但 model_path 缺失/坏文件 → 优雅降级为不启用，不抛异常。"""
    paths, _feats, _strengths, _ood, _csp, _trials = _make_domain(tmp_path)
    cfg = _engine_cfg(paths, enabled=True)
    cfg.ood = dataclasses.replace(cfg.ood, model_path=str(tmp_path / "nope.joblib"))
    eng = DecoderEngine(cfg)  # 不应抛错
    assert eng.ood is None


def test_engine_ood_indomain_still_classifies(tmp_path):
    """开关开启：训练域内强信号（重复 4 段同侧）不被误杀，vote 稳定后输出非 idle。"""
    paths, _feats, strengths, _ood, _csp, trials = _make_domain(tmp_path)
    # 选用训练域最强 trial，确保该输入远离低强度段（不被 strength 判据误杀）
    idx = int(np.argmax(strengths))
    cfg = _engine_cfg(paths, enabled=True)
    eng = DecoderEngine(cfg)
    seg = np.concatenate([trials[idx]] * 4, axis=1)  # 同侧重复 4 段（2s×4），域内强信号
    labels_out = []
    t0 = 0.0
    for i in range(0, seg.shape[1], 25):
        s = seg[:, i:i + 25]
        if s.shape[1] < 25:
            break
        for o in eng.push(EEGChunk(data=s, sfreq=250.0, t0=t0)):
            labels_out.append(o.label)
        t0 += 25.0 / 250.0
    assert any(l != "idle" for l in labels_out)
