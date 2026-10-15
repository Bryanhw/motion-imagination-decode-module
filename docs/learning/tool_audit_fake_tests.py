"""假测试审计：本目录所有"防护性断言"是否真的能抓到 bug？

一个断言只有在"注入对应 bug 后会失败"时才有价值。
本脚本对每条断言注入它应该防住的那个 bug，确认它确实失败。

被审计的断言：
  A. T3 等价性（多种块长）
  B. T4 块边界无跳变
  C. reset() 清空状态
  D. StreamFilter.state 形状约定
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
from scipy.signal import sosfilt

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "bci-decoder"))

from bci_decoder.config import PreprocessConfig                       # noqa: E402
from bci_decoder.pipeline import preprocess as pp                     # noqa: E402
from bci_decoder.pipeline.preprocess import Preprocessor, StreamFilter  # noqa: E402

SFREC, NCH, CHUNK = 250.0, 8, 25
_ORIG_PROCESS = StreamFilter.process
_ORIG_RESET = StreamFilter.reset


def make_eeg(n_samples=2000, seed=0, n_channels=NCH):
    rng = np.random.default_rng(seed)
    t = np.arange(n_samples) / SFREC
    sig = 15.0 * np.sin(2 * np.pi * 10.0 * t)
    drift = 20.0 * np.sin(2 * np.pi * 0.3 * t)
    noise = 5.0 * rng.standard_normal((n_channels, n_samples))
    return sig[None, :] * np.linspace(0.8, 1.2, n_channels)[:, None] + drift + noise


def feed(pre, x, chunk):
    return np.concatenate([pre.process(x[:, i:i + chunk])[0]
                           for i in range(0, x.shape[1], chunk)], axis=1)


def whole(x):
    return Preprocessor(PreprocessConfig(), NCH, SFREC).process(x)[0]


# ---- 注入各种 bug 的版本 ----
def bug_no_state(self, x):
    """bug 1：不跨块传状态（骨架注释里警告的那个坑）"""
    return sosfilt(self.sos, x)


def bug_state_never_persists(self, x):
    """bug 2：形状完全正确，但状态永远不累积（"走过场"式实现）。

    这是比 axis 写错**更隐蔽**的一类 bug：state 属性的形状、初始化、
    reset 全都对，静态检查挑不出毛病，只有"行为等价性"测试才能抓到。
    """
    y, _ = sosfilt(self.sos, x, zi=np.zeros_like(self.state))   # 每次都用零状态，但不写回
    return y


def bug_wrong_axis(self, x):
    """bug 3：axis 写错（多通道当单通道处理）—— 实测会抛 ValueError。"""
    y, self.state = sosfilt(self.sos, x.ravel(), zi=self.state.ravel()[:2].reshape(1, 1, 2))
    return y.reshape(x.shape)


def bug_reset_noop(self):
    """bug 4：reset 什么都不做（切被试时残留旧记忆）"""
    return None


# ---- 各条断言 ----
def check_A_state_continuity():
    x = make_eeg(2000)
    y = feed(Preprocessor(PreprocessConfig(), NCH, SFREC), x, CHUNK)
    return bool(np.allclose(y, whole(x), atol=1e-8))


def check_B_no_boundary_step():
    chunk = CHUNK
    x = make_eeg(2000)
    y = feed(Preprocessor(PreprocessConfig(), NCH, SFREC), x, chunk)
    diff = np.abs(np.diff(y, axis=1))
    bpos = np.arange(chunk, y.shape[1], chunk) - 1
    bpos = bpos[bpos < diff.shape[1]]
    interior = np.setdiff1d(np.arange(diff.shape[1]), bpos)
    return bool(diff[:, bpos].max() <= np.percentile(diff[:, interior], 99.9) * 1.5)


def check_C_reset_clears():
    x1, x2 = make_eeg(500, seed=1), make_eeg(500, seed=2)
    pre = Preprocessor(PreprocessConfig(), NCH, SFREC)
    pre.process(x1)
    pre.reset()
    y_after = pre.process(x2)[0]
    y_fresh = Preprocessor(PreprocessConfig(), NCH, SFREC).process(x2)[0]
    return bool(np.allclose(y_after, y_fresh, atol=1e-12))


def check_D_state_shape():
    sos = pp.design_bandpass(SFREC, 8.0, 30.0, 4)
    return StreamFilter(sos, NCH).state.shape == (sos.shape[0], NCH, 2)


CHECKS = [
    ("A. T3 分块==整段（块长25）", check_A_state_continuity, bug_no_state, "不传状态"),
    ("B. T4 块边界无跳变", check_B_no_boundary_step, bug_no_state, "不传状态"),
    ("C. reset() 清空状态", check_C_reset_clears, None, "reset 空实现"),
    ("D. state 形状约定", check_D_state_shape, bug_state_never_persists,
     "状态不累积（形状仍正确）"),
]

print("=" * 82)
print("假测试审计：注入 bug 后，断言是否失败？")
print("=" * 82)
print("%-28s %-14s %-14s %s" % ("断言", "正常时", "注入bug后", "判定"))
print("-" * 82)

verdicts = []
for name, check, bug, bug_desc in CHECKS:
    # 正常
    StreamFilter.process, StreamFilter.reset = _ORIG_PROCESS, _ORIG_RESET
    normal = check()

    # 注入 bug
    StreamFilter.process, StreamFilter.reset = _ORIG_PROCESS, _ORIG_RESET
    if bug is not None:
        StreamFilter.process = bug
    else:
        StreamFilter.reset = bug_reset_noop
    broken = check()

    StreamFilter.process, StreamFilter.reset = _ORIG_PROCESS, _ORIG_RESET

    if normal and not broken:
        verdict = "有效 [OK]"
    elif normal and broken:
        verdict = "假测试 [FAKE]"
    else:
        verdict = "实现有问题 [BUG]"
    verdicts.append((name, verdict, bug_desc))
    print("%-28s %-14s %-14s %s" % (name, "通过" if normal else "失败",
                                     "失败" if not broken else "通过", verdict))

print()
bad = [(n, d) for n, v, d in verdicts if v != "有效 [OK]"]
for name, verdict, desc in verdicts:
    if verdict != "有效 [OK]":
        print("  ⚠️  %s 在注入「%s」后仍然通过 → %s" % (name, desc, verdict))

if not bad:
    print("结论：全部 %d 条断言都能抓到它应该防的 bug，不是假测试。" % len(CHECKS))
else:
    print()
    print("结论：形状类断言（D）**天生抓不到行为类 bug**。")
    print("      state 的形状、初始化、reset 全都写对，仍然可以让状态永不累积；")
    print("      只有 A（行为等价性）能抓到它。")
    print("      → 所以 T3 那条『分块喂入 == 一次喂入』才是本项目最有价值的一条测试。")

# 补充：axis 写错到底会不会报错？
StreamFilter.process = bug_wrong_axis
try:
    feed(Preprocessor(PreprocessConfig(), NCH, SFREC), make_eeg(500), CHUNK)
    print("\n补充观察：axis 写错的实现**没有**抛异常（我原先的猜测是错的）。")
except Exception as e:
    print("\n补充观察：axis 写错的实现会抛异常 → %s: %s" % (type(e).__name__, e))
    print("      也就是说 **改错了 axis 会立刻炸，属于'响亮的错误'**，")
    print("      真正危险的是不报错的那类：不传 state、状态不累积。")
finally:
    StreamFilter.process = _ORIG_PROCESS
