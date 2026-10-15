"""T3/T4 参考实现：因果滤波状态连续性测试（练习 3 的标准答案）

这是《骨架主链路导读》第 9.1 节练习 3 的参考实现，也是《MVP 规格说明书》
附录 B 里 T3、T4 两个用例的完整写法。

运行（必须在 bci-decoder 目录下，否则 import bci_decoder 会失败）：

    cd bci-decoder
    .venv\\Scripts\\python.exe -m pytest ..\\docs\\learning\\test_t3_t4_reference.py -v

============================================================================
先说一个重要发现：骨架里**已经有** T3 的雏形，别白写一遍
============================================================================

`bci-decoder/tests/test_pipeline.py::test_preprocessor_shape_and_streaming_state`
第 22–25 行就是：

    pre2 = Preprocessor(cfg, n_channels=3, sfreq=250.0)
    whole, _ = pre2.process(np.concatenate([x, x], axis=1))
    assert np.allclose(np.concatenate([y1, y2], axis=1), whole, atol=1e-8)

我已实测验证过这条断言**是有效的，不是假测试**：
  - 正确实现（跨块传 state）：最大误差 0.000e+00 → 通过
  - 错误实现（不传 state）  ：最大误差 6.821e-01 → 失败

**所以练习 3 的正确做法不是"再写一个一样的"，而是把它做扎实**，补上骨架漏掉的四点：

  1. 只用了一种块长（25 点）。真正的风险在**块长与滤波器阶数的组合**上，
     所以要参数化扫描多种块长；
  2. 没有覆盖 T4：块边界处**不应该有一阶跳变**（阶跃是"特征抖动"的直接来源）；
  3. 没有覆盖 `reset()` 之后的行为（校准流程切被试时会用到）；
  4. 没有多通道测试（骨架那条用的是 3 通道，而项目冻结值是 8 通道）。

下面的测试把这四点补齐，对应的就是《MVP 规格说明书》附录 B 的 T3、T4。
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

# 允许从仓库根目录或 docs/learning 直接运行
_BCI_ROOT = Path(__file__).resolve().parents[2] / "bci-decoder"
if str(_BCI_ROOT) not in sys.path:
    sys.path.insert(0, str(_BCI_ROOT))

from bci_decoder.config import PreprocessConfig              # noqa: E402
from bci_decoder.pipeline.preprocess import (                # noqa: E402
    Preprocessor,
    StreamFilter,
    design_bandpass,
)

SFREC = 250.0
N_CHANNELS = 8          # 项目冻结值（MVP 规格 5.1）
CHUNK_SAMPLES = 25      # 冻结值 100 ms @ 250 Hz


def _make_eeg(n_channels: int = N_CHANNELS, n_samples: int = 2500, seed: int = 0) -> np.ndarray:
    """造一段"像脑电"的数据：μ 节律 + 噪声 + 慢漂移。"""
    rng = np.random.default_rng(seed)
    t = np.arange(n_samples) / SFREC
    signal = 15.0 * np.sin(2 * np.pi * 10.0 * t)
    drift = 20.0 * np.sin(2 * np.pi * 0.3 * t)
    noise = 5.0 * rng.standard_normal((n_channels, n_samples))
    return signal[None, :] * np.linspace(0.8, 1.2, n_channels)[:, None] + drift + noise


def _feed_in_chunks(pre: Preprocessor, x: np.ndarray, chunk: int) -> np.ndarray:
    """把数据按固定块长分块喂进去，返回拼起来的输出。"""
    pieces = [pre.process(x[:, i:i + chunk])[0] for i in range(0, x.shape[1], chunk)]
    return np.concatenate(pieces, axis=1)


# ---------------------------------------------------------------------------
# T3 核心断言：分块喂入 == 一次喂入
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("chunk", [6, 12, 25, 50, 125, 500, 2500])
def test_T3_streaming_equals_whole(chunk: int):
    """T3：因果滤波状态连续性 —— 任意块长下，分块喂入必须等于一次喂入。

    容差取 1e-8（骨架原值）。这是**唯一正确的等价性判据**：
    它同时覆盖了"滤波状态是否传递"和"预处理链每一步是否无状态/状态正确"。
    """
    x = _make_eeg()

    pre_stream = Preprocessor(PreprocessConfig(), N_CHANNELS, SFREC)
    y_stream = _feed_in_chunks(pre_stream, x, chunk)

    pre_whole = Preprocessor(PreprocessConfig(), N_CHANNELS, SFREC)
    y_whole, _ = pre_whole.process(x)

    assert y_stream.shape == y_whole.shape == x.shape
    assert np.allclose(y_stream, y_whole, atol=1e-8), (
        f"块长 {chunk} 时，分块喂入与一次喂入不一致："
        f"最大误差 {np.max(np.abs(y_stream - y_whole)):.3e}。"
        "最常见原因：StreamFilter.process 没有把 zi 状态存回 self.state。"
    )


def test_T3_streaming_equals_whole_with_different_chunk_sizes_mixed():
    """T3 加强版：块长**不均匀**时也必须等价（真实数据流会有抖动）。"""
    x = _make_eeg(n_samples=2000)
    chunks = [7, 25, 100, 13, 250, 5]      # 故意不均匀

    pre = Preprocessor(PreprocessConfig(), N_CHANNELS, SFREC)
    pieces, pos = [], 0
    for c in chunks:
        if pos >= x.shape[1]:
            break
        part = x[:, pos:pos + c]
        pieces.append(pre.process(part)[0])
        pos += c
    if pos < x.shape[1]:
        pieces.append(pre.process(x[:, pos:])[0])
    y_stream = np.concatenate(pieces, axis=1)

    pre_whole = Preprocessor(PreprocessConfig(), N_CHANNELS, SFREC)
    y_whole, _ = pre_whole.process(x)

    assert np.allclose(y_stream, y_whole, atol=1e-8)


# ---------------------------------------------------------------------------
# T4：块边界无跳变
# ---------------------------------------------------------------------------
def test_T4_no_step_at_chunk_boundaries():
    """T4：滤波前后在块边界处不应出现阶跃。

    判据：以固定块长分块处理时，边界处的相邻样本差
    **不应该显著大于**同一信号在块内（非边界）的相邻样本差。

    这是"特征抖动"的直接来源：阶跃会污染窗口内的频带功率。
    """
    chunk = CHUNK_SAMPLES
    x = _make_eeg(n_samples=2000)
    y = _feed_in_chunks(Preprocessor(PreprocessConfig(), N_CHANNELS, SFREC), x, chunk)

    diff = np.abs(np.diff(y, axis=1))
    boundary_pos = np.arange(chunk, y.shape[1], chunk) - 1      # 每个边界的前一个样本
    boundary_pos = boundary_pos[boundary_pos < diff.shape[1]]
    interior = np.setdiff1d(np.arange(diff.shape[1]), boundary_pos)

    max_boundary = float(diff[:, boundary_pos].max())
    p999_interior = float(np.percentile(diff[:, interior], 99.9))

    assert max_boundary <= p999_interior * 1.5, (
        f"块边界出现跳变：边界处最大差分 {max_boundary:.4f}，"
        f"块内 99.9 分位 {p999_interior:.4f}。"
        "说明块之间没有正确延续滤波器状态。"
    )


# ---------------------------------------------------------------------------
# T3 反面对照：证明这条断言真的能抓到 bug
# ---------------------------------------------------------------------------
def test_T3_assertion_is_not_a_fake_test():
    """证明 T3 断言有效：把状态传递去掉后，等价性断言必须失败。

    做法：临时把 StreamFilter.process 换成"不传 zi"的错误实现，
    用 pytest.raises 断言"这时候 np.allclose 会为假"。

    这个测试的价值在于：**它证明第一条测试不是假测试**。
    在真实项目里，"测试通过了"和"测试有用"是两件事 ——
    一个永远通过的测试，等于没有测试。
    """
    x = _make_eeg(n_samples=1000, seed=7)
    chunk = CHUNK_SAMPLES

    original = StreamFilter.process

    def broken_process(self, x_):
        # 错误写法：每块都从零状态开始（这正是骨架注释警告的那个坑）
        from scipy.signal import sosfilt
        return sosfilt(self.sos, x_)

    StreamFilter.process = broken_process
    try:
        pre = Preprocessor(PreprocessConfig(), N_CHANNELS, SFREC)
        y_broken = _feed_in_chunks(pre, x, chunk)

        pre_whole = Preprocessor(PreprocessConfig(), N_CHANNELS, SFREC)
        y_whole, _ = pre_whole.process(x)

        max_err = float(np.max(np.abs(y_broken - y_whole)))
        assert max_err > 1e-3, (
            "去掉状态传递后误差仍然很小，说明这个等价性断言防不住 bug（假测试）"
        )
        assert not np.allclose(y_broken, y_whole, atol=1e-8)
    finally:
        StreamFilter.process = original       # 务必还原，避免污染其他测试


# ---------------------------------------------------------------------------
# reset() 行为：校准流程切被试时会用到
# ---------------------------------------------------------------------------
def test_reset_clears_filter_state():
    """reset() 之后必须回到"全新滤波器"的状态。

    ④ 阶段校准流程会切换被试/重新开始，若 reset 不干净，
    新被试的第一段数据会被上一个被试的滤波器记忆污染。
    """
    x1 = _make_eeg(n_samples=500, seed=1)
    x2 = _make_eeg(n_samples=500, seed=2)

    pre = Preprocessor(PreprocessConfig(), N_CHANNELS, SFREC)
    pre.process(x1)
    pre.reset()
    y_after_reset, _ = pre.process(x2)

    fresh = Preprocessor(PreprocessConfig(), N_CHANNELS, SFREC)
    y_fresh, _ = fresh.process(x2)

    assert np.allclose(y_after_reset, y_fresh, atol=1e-12)


# ---------------------------------------------------------------------------
# 底层单元：StreamFilter 的状态形状与 sosfilt 约定必须一致
# ---------------------------------------------------------------------------
def test_stream_filter_state_shape_matches_scipy_convention():
    """state 形状必须是 (n_sections, n_channels, 2)。

    这是 scipy 在多通道 + axis=-1 时的约定。形状写错会直接抛异常，
    但把 axis 写错（例如 axis=0）**不会报错**，只会算错 ——
    所以这里把约定显式断言出来，当成"文档化测试"。
    """
    sos = design_bandpass(SFREC, 8.0, 30.0, order=4)
    sf = StreamFilter(sos, N_CHANNELS)
    assert sf.state.shape == (sos.shape[0], N_CHANNELS, 2)

    y = sf.process(_make_eeg(n_samples=100, seed=3))
    assert y.shape == (N_CHANNELS, 100)
    # 处理后状态必须被更新（不再是全零）
    assert np.any(sf.state != 0.0)

    sf.reset()
    assert np.all(sf.state == 0.0)
