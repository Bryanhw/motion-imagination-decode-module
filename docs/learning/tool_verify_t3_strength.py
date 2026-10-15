"""关键验证：骨架的 T3 断言"真的能抓到 bug 吗"？

做法：把 StreamFilter 的 state 传递去掉（模拟最容易犯的错），
看骨架那条断言（分块 == 整段）是否**失败**。
如果去掉状态后测试仍然通过，说明这个测试是"假测试"，防不住任何东西。
"""
import sys
from pathlib import Path

import numpy as np
from scipy.signal import sosfilt

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "bci-decoder"))

from bci_decoder.config import PreprocessConfig          # noqa: E402
from bci_decoder.pipeline import preprocess as pp        # noqa: E402


def run_case(label, patch_state: bool):
    cfg = PreprocessConfig()
    pre = pp.Preprocessor(cfg, n_channels=3, sfreq=250.0)

    if patch_state:
        # 把"带状态"改成"每块重新开始"：去掉 zi 传递
        def broken_process(self, x):
            y = self.sos.dot(np.zeros(0)) if False else None  # 占位，避免 lint
            y = sosfilt(self.sos, x)                          # 不传 zi
            return y

        pp.StreamFilter.process = broken_process

    rng = np.random.default_rng(0)
    x = rng.standard_normal((3, 25))

    y1, _ = pre.process(x)
    y2, _ = pre.process(x)

    pre2 = pp.Preprocessor(cfg, n_channels=3, sfreq=250.0)
    whole, _ = pre2.process(np.concatenate([x, x], axis=1))

    streamed = np.concatenate([y1, y2], axis=1)
    max_err = float(np.max(np.abs(streamed - whole)))
    passed = bool(np.allclose(streamed, whole, atol=1e-8))
    print("  %-22s 最大误差=%.3e  断言结果=%s" % (label, max_err, "通过" if passed else "失败"))
    return passed


print("=== 骨架 test_preprocessor_shape_and_streaming_state 的抓 bug 能力 ===")
ok_normal = run_case("正确实现（带状态）", patch_state=False)
ok_broken = run_case("错误实现（不传状态）", patch_state=True)

print()
if ok_normal and not ok_broken:
    print("  结论：这个断言**有效** —— 正确实现通过、错误实现失败，能真正防住 bug。")
elif ok_normal and ok_broken:
    print("  结论：⚠️ 这是**假测试** —— 去掉状态它仍然通过，防不住任何东西！")
else:
    print("  结论：⚠️ 异常 —— 正确实现竟然没通过，说明测试本身写错了。")
