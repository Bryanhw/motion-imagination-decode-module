"""calibrate.py 真采分支（--real-data/--labels）防御校验的单元测试。

覆盖：真采正确路径 trial 切分、通道数不符显式抛错、标签非法显式抛错、
索引写法兼容、二维标签拒绝。通道顺序即语义（红线 4），契约违背必须
报错而非静默错位。
"""

from __future__ import annotations

import importlib.util
import os
from types import SimpleNamespace

import numpy as np
import pytest

from bci_decoder.config import Config, DEFAULT_CH_NAMES

# scripts/ 不是包，用 importlib 从文件加载 calibrate.py
# （calibrate.py 顶层会自行把 bci-decoder/ 与 scripts/ 加入 sys.path）
_SCRIPTS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts")
_SPEC = importlib.util.spec_from_file_location(
    "calibrate", os.path.join(_SCRIPTS, "calibrate.py")
)
calibrate = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(calibrate)


def _cfg() -> Config:
    c = Config()
    assert len(c.source.ch_names) == 8  # 与 configs/default.yaml 对齐
    assert c.source.sfreq == 250.0
    assert c.classifier.classes == ["left", "right"]
    return c


def _args(real_data: str, labels: str) -> SimpleNamespace:
    return SimpleNamespace(real_data=real_data, labels=labels, trial_seconds=2.0, config="")


def test_real_data_ok_cuts_trials(tmp_path):
    cfg = _cfg()
    step = int(cfg.source.sfreq * 2.0)  # 500
    raw = np.zeros((len(DEFAULT_CH_NAMES), 3 * step))
    labels = np.array(["left", "right", "left"])
    rp, lp = tmp_path / "raw.npy", tmp_path / "labels.npy"
    np.save(rp, raw)
    np.save(lp, labels)

    trials, got, source = calibrate._prepare_trials(_args(str(rp), str(lp)), cfg)

    assert source == "real"
    assert len(trials) == 3
    assert trials[0].shape == (len(DEFAULT_CH_NAMES), step)
    assert np.array_equal(got, labels)


def test_real_data_wrong_channel_count_raises(tmp_path):
    cfg = _cfg()
    raw = np.zeros((7, 1500))  # 缺一个通道
    labels = np.array(["left", "right"])
    rp, lp = tmp_path / "raw.npy", tmp_path / "labels.npy"
    np.save(rp, raw)
    np.save(lp, labels)

    with pytest.raises(ValueError, match="通道数不符"):
        calibrate._prepare_trials(_args(str(rp), str(lp)), cfg)


def test_real_data_invalid_label_raises(tmp_path):
    cfg = _cfg()
    raw = np.zeros((len(DEFAULT_CH_NAMES), 1500))
    labels = np.array(["left", "up"])  # 'up' 不在 classes
    rp, lp = tmp_path / "raw.npy", tmp_path / "labels.npy"
    np.save(rp, raw)
    np.save(lp, labels)

    with pytest.raises(ValueError, match="未知类别"):
        calibrate._prepare_trials(_args(str(rp), str(lp)), cfg)


def test_real_data_int_labels_ok(tmp_path):
    cfg = _cfg()
    raw = np.zeros((len(DEFAULT_CH_NAMES), 1500))
    labels = np.array([0, 1, 0])  # 0..n-1 索引写法也接受
    rp, lp = tmp_path / "raw.npy", tmp_path / "labels.npy"
    np.save(rp, raw)
    np.save(lp, labels)

    trials, got, source = calibrate._prepare_trials(_args(str(rp), str(lp)), cfg)
    assert source == "real"
    assert len(trials) == 3


def test_real_data_2d_labels_raises(tmp_path):
    cfg = _cfg()
    raw = np.zeros((len(DEFAULT_CH_NAMES), 1500))
    labels = np.zeros((3, 1))  # 二维标签非法
    rp, lp = tmp_path / "raw.npy", tmp_path / "labels.npy"
    np.save(rp, raw)
    np.save(lp, labels)

    with pytest.raises(ValueError, match="一维"):
        calibrate._prepare_trials(_args(str(rp), str(lp)), cfg)
