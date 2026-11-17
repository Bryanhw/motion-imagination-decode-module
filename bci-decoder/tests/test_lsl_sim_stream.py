"""lsl_sim_stream.py 本地仿真流的单元测试。

覆盖：通道顺序红线（不重排）、数据形状/dtype、确定性复现、枕区 alpha 判读友好、
几何一致性在数据层成立、推流节奏（样本数与通道维）、关闭 alpha 的对照。
纯数据校验，不做任何性能/准确率断言。
"""

from __future__ import annotations

import importlib.util
import os

import numpy as np
import pytest
from scipy.signal import welch

_SCRIPTS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts")
_SPEC = importlib.util.spec_from_file_location(
    "lsl_sim_stream", os.path.join(_SCRIPTS, "lsl_sim_stream.py")
)
sim = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(sim)

EXPECTED_CH_ORDER = ["C3", "Cz", "C4", "CP3", "CP4", "P3", "P4", "Oz"]


def band_power(sig, sfreq, lo=8.0, hi=13.0):
    """8-13Hz 频带功率（绝对），用于对照仿真结构。"""
    f, p = welch(sig - sig.mean(), fs=sfreq, nperseg=min(len(sig), int(2 * sfreq)))
    m = (f >= lo) & (f <= hi)
    return float(p[m].sum())


def test_channel_order_pinned():
    # 红线 4：顺序即语义，仿真流顺序必须与项目固定顺序一致
    assert list(sim.SIM_CH_NAMES) == EXPECTED_CH_ORDER


def test_simulate_block_shape_dtype():
    data = sim.simulate_block(duration_sec=2.0)
    assert data.shape == (8, 500)
    assert data.dtype == np.float32
    assert np.isfinite(data).all()


def test_simulate_block_deterministic():
    a = sim.simulate_block(duration_sec=2.0, seed=42)
    b = sim.simulate_block(duration_sec=2.0, seed=42)
    assert np.array_equal(a, b)
    c = sim.simulate_block(duration_sec=2.0, seed=1)
    assert not np.array_equal(a, c)


def test_alpha_channel_dominant():
    # 枕区 Oz 的 8-13Hz 功率应明显强于非枕区（C3），保证 selftest 的 alpha 判读能找到枕区
    data = sim.simulate_block(duration_sec=10.0, seed=0)
    names = sim.SIM_CH_NAMES
    p_oz = band_power(data[names.index("Oz")], 250.0)
    p_c3 = band_power(data[names.index("C3")], 250.0)
    p_c4 = band_power(data[names.index("C4")], 250.0)
    assert p_oz > p_c3 * 1.5
    assert p_oz > p_c4 * 1.5


def test_neighbor_correlation_gt_cross():
    # 几何一致性：相邻（C3-CP3）相关应大于对侧远距（C3-P4），判读才不会误报
    data = sim.simulate_block(duration_sec=10.0, seed=0)
    names = sim.SIM_CH_NAMES
    a = data[names.index("C3")] - data[names.index("C3")].mean()
    b = data[names.index("CP3")] - data[names.index("CP3")].mean()
    c = data[names.index("P4")] - data[names.index("P4")].mean()
    r_adj = float(np.corrcoef(a, b)[0, 1])
    r_cross = float(np.corrcoef(a, c)[0, 1])
    assert r_adj > r_cross


def test_run_pushes_expected_shape_and_count():
    collected = []
    data = sim.simulate_block(n_ch=8, sfreq=100.0, duration_sec=1.0, seed=0)
    sent = sim.run(collected.append, data, sfreq=100.0)
    assert sent == 100
    assert len(collected) == 100
    assert all(len(row) == 8 for row in collected)
    assert all(np.isfinite(row).all() for row in collected)


def test_no_alpha_reduces_occipital_power():
    # 关闭 alpha 后，枕区 alpha 功率不应显著高于有 alpha 的情形（对照，证明开关有效）
    on = sim.simulate_block(duration_sec=10.0, seed=0, alpha=True)
    off = sim.simulate_block(duration_sec=10.0, seed=0, alpha=False)
    oz = sim.SIM_CH_NAMES.index("Oz")
    p_on = band_power(on[oz], 250.0)
    p_off = band_power(off[oz], 250.0)
    assert p_on > p_off * 1.5


def test_invalid_nch_rejected(monkeypatch):
    # 参数边界：--n-ch 超范围直接中文报错（发生在连接 pylsl 之前，无需真发布流）
    import sys

    monkeypatch.setattr(sys, "argv", ["lsl_sim_stream.py", "--n-ch", "99"])
    with pytest.raises(SystemExit) as e:
        sim.main()
    assert "n-ch 应在 1..8 之间" in str(e.value)
