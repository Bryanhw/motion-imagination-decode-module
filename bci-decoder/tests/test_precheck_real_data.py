"""precheck_real_data.py「真采数据格式预检」单元测试。

覆盖：正常 PASS 与采样率推断、采样率不匹配强警告、通道数错误、标签非法、
样本数不可整除警告、长度不足 FAIL、索引标签兼容、报告落盘。纯数据校验，不做性能评估。
"""

from __future__ import annotations

import importlib.util
import json
import os

import numpy as np
import pytest

from bci_decoder.config import Config, DEFAULT_CH_NAMES

_SCRIPTS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts")
_SPEC = importlib.util.spec_from_file_location(
    "precheck_real_data", os.path.join(_SCRIPTS, "precheck_real_data.py")
)
precheck = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(precheck)


@pytest.fixture
def cfg():
    c = Config()
    assert len(c.source.ch_names) == 8
    assert c.source.sfreq == 250.0
    return c


def test_pass_infers_sfreq(cfg):
    raw = np.zeros((8, 1500))
    labels = np.array(["left", "right", "left"])
    r = precheck._validate_and_report(raw, labels, cfg, 2.0)
    assert r["verdict"] == "PASS"
    assert r["ok"] is True
    assert r["trial"]["inferred_sfreq_hz"] == 250.0
    assert r["trial"]["sfreq_match"] is True
    assert r["labels"]["counts"] == {"left": 2, "right": 1}


def test_sfreq_mismatch_warns(cfg):
    # 模拟设备 500Hz：样本数翻倍，(8, 1000×3)
    raw = np.zeros((8, 3000))
    labels = np.array(["left", "right", "left"])
    r = precheck._validate_and_report(raw, labels, cfg, 2.0)
    assert r["verdict"] == "WARN"
    assert r["ok"] is False
    assert r["trial"]["inferred_sfreq_hz"] == 500.0
    assert r["trial"]["sfreq_match"] is False
    assert any("采样率" in w for w in r["warnings"])


def test_wrong_channel_count_fails(cfg):
    raw = np.zeros((7, 1500))
    labels = np.array(["left", "right"])
    r = precheck._validate_and_report(raw, labels, cfg, 2.0)
    assert r["verdict"] == "FAIL"
    assert any("通道数" in e for e in r["errors"])


def test_invalid_label_fails(cfg):
    raw = np.zeros((8, 1500))
    labels = np.array(["left", "up"])
    r = precheck._validate_and_report(raw, labels, cfg, 2.0)
    assert r["verdict"] == "FAIL"
    assert any("未知类别" in e for e in r["errors"])


def test_uneven_samples_warns(cfg):
    raw = np.zeros((8, 1501))  # 不能被 3 整除
    labels = np.array(["left", "right", "left"])
    r = precheck._validate_and_report(raw, labels, cfg, 2.0)
    assert r["verdict"] == "WARN"
    assert any("整除" in w for w in r["warnings"])


def test_too_short_fails(cfg):
    raw = np.zeros((8, 100))
    labels = np.array(["left", "right", "left"])
    r = precheck._validate_and_report(raw, labels, cfg, 2.0)
    assert r["verdict"] == "FAIL"
    assert any("长度不足" in e for e in r["errors"])


def test_int_labels_supported(cfg):
    raw = np.zeros((8, 1500))
    labels = np.array([0, 1, 0])
    r = precheck._validate_and_report(raw, labels, cfg, 2.0)
    assert r["verdict"] == "PASS"
    assert r["labels"]["counts"] == {"left": 2, "right": 1}


def test_report_saved(tmp_path):
    result = {
        "verdict": "PASS",
        "errors": [],
        "warnings": [],
        "raw": {"shape": [8, 1500], "n_ch": 8},
        "trial": {"inferred_sfreq_hz": 250.0, "sfreq_match": True},
        "labels": {"n_trials": 3, "counts": {"left": 2, "right": 1}},
        "config": {
            "sfreq": 250.0,
            "trial_seconds": 2.0,
            "step_samples": 500,
            "ch_names": list(DEFAULT_CH_NAMES),
            "classes": ["left", "right"],
        },
    }
    paths = precheck.write_report(result, "alice", str(tmp_path))
    assert os.path.exists(paths["json"])
    assert os.path.exists(paths["md"])
    with open(paths["json"], encoding="utf-8") as f:
        assert json.load(f)["verdict"] == "PASS"
    with open(paths["md"], encoding="utf-8") as f:
        assert "真采数据格式预检报告" in f.read()
