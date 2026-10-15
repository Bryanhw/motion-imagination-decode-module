"""验证导读文档里的技术断言是否成立（一次性核对脚本）。"""
import sys

import numpy as np
from scipy.signal import butter, sosfilt, sosfiltfilt

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

sfreq = 250.0
sos = butter(4, [8.0, 30.0], btype="bandpass", fs=sfreq, output="sos")
rng = np.random.default_rng(3)

print("=== 断言 1：CAR 写成 axis=1 会静默做错（与 axis=0 差别很大）===")
n = 2000
x = np.zeros((8, n))
for c in range(8):
    x[c] = rng.standard_normal(n) * 5.0 + (c + 1) * 2.0      # 各通道有不同直流偏置
x += 10.0 * np.sin(2 * np.pi * 7 * np.arange(n) / sfreq)      # 所有通道共有的干扰
car_ok = x - x.mean(axis=0, keepdims=True)                    # 正确：按时间点减所有通道均值
car_bad = x - x.mean(axis=1, keepdims=True)                   # 错误：每个通道减自己的均值
print("  正确 CAR(axis=0) 各通道均值: ", np.round(car_ok.mean(axis=1), 3))
print("  错误 CAR(axis=1) 各通道均值: ", np.round(car_bad.mean(axis=1), 3))
print("  两者最大差异: %.3f µV  → 都不报错，但结果完全不同" % np.max(np.abs(car_ok - car_bad)))

print()
print("=== 断言 2：窗长 2.0s@250Hz = 500 点；特征维度 = 2 频带 × 8 通道 = 16 ===")
print("  窗长样本数:", int(round(2.0 * sfreq)), " 特征维度:", 2 * 8)

print()
print("=== 断言 3：未训练分类器 → 均匀概率 0.5 → 低于门限 0.6 → 恒 idle ===")


def stabilizer_sim(probs, min_conf=0.6, vote_window=3, ema_alpha=0.4):
    """照抄骨架 postprocess.py 的逻辑，验证'未训练恒 idle'。"""
    ema = None
    votes = []
    current = "idle"
    out = []
    for p in probs:
        p = np.asarray(p, dtype=float).ravel()
        ema = p.copy() if ema is None else ema_alpha * p + (1 - ema_alpha) * ema
        ema = ema / ema.sum()
        top = int(np.argmax(ema))
        conf = float(ema[top])
        votes.append(top)
        votes = votes[-vote_window:]
        stable = len(votes) == vote_window and len(set(votes)) == 1
        if not stable:
            out.append((current, conf))
            continue
        current = "idle" if conf < min_conf else (["left", "right"][top] if top < 2 else "idle")
        out.append((current, conf))
    return out


uniform = [np.array([0.5, 0.5])] * 10
outs = stabilizer_sim(uniform)
labels = {o[0] for o in outs}
print("  输入 10 次均匀概率 [0.5, 0.5] → 输出 label 集合:", labels)
print("  是否符合红线 R-2（恒 idle）:", "是" if labels == {"idle"} else "否 ❌")

confident = [np.array([0.9, 0.1])] * 10
outs2 = stabilizer_sim(confident)
print("  对照：连续 10 次 [0.9, 0.1] → 输出 label 集合:", {o[0] for o in outs2})
print("  （说明稳定化要连续 3 次一致才允许切换，前 2 次仍是 idle）")

print()
print("=== 断言 4：分块流式 == 一次性（T3 用例的核心断言）===")
raw = rng.standard_normal(2500) * 10
y_once = sosfilt(sos, raw)
for cs in (25, 50, 125):
    state = np.zeros((sos.shape[0], 2))
    pieces = []
    for i in range(0, len(raw), cs):
        y, state = sosfilt(sos, raw[i:i + cs], zi=state)
        pieces.append(y)
    err = float(np.max(np.abs(y_once - np.concatenate(pieces))))
    print("  块长 %3d 样本 → 最大误差 %.3e" % (cs, err))
