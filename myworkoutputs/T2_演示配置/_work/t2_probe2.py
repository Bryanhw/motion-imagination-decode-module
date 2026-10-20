# 探测2：验证 demo_csp/demo_lda 判别力 + OOD 行为（T2c 工程自检）
from __future__ import annotations
import os, sys
import numpy as np

os.chdir(r"D:\校企合作项目\bci-decoder")
sys.path.insert(0, r"D:\校企合作项目\bci-decoder")
from bci_decoder.config import Config
from bci_decoder.core import DecoderEngine
from bci_decoder.types import EEGChunk

CFG = r"D:\校企合作项目\bci-decoder\configs\demo_weak.yaml"
SFREQ, N_CH, SECONDS, CHUNK = 250.0, 8, 40.0, 25
NAMES = ["C3", "Cz", "C4", "CP3", "CP4", "P3", "P4", "Oz"]


def gen(style: str):
    n = int(SFREQ * SECONDS)
    rng = np.random.default_rng(9)
    t = np.arange(n) / SFREQ
    alpha = np.sin(2 * np.pi * 10.0 * t)
    lab = np.zeros(n, dtype=int)
    if style in ("pure_right", "weak_right"):
        lab[:] = 1
    if style == "split":
        lab[int(n * 0.5):] = 1
    g = np.ones((N_CH, n))
    g[0] = 1.0 + 0.8 * (1 - lab)
    g[2] = 1.0 + 0.8 * lab
    if style == "weak_right":
        # 弱 right：C4 增益压缩 + 高噪声
        g = np.ones((N_CH, n))
        g[0] = 1.0
        g[2] = 1.0 + 0.1 * lab
        return 2.0 * alpha[None, :] * g + 25.0 * rng.standard_normal((N_CH, n))
    return 15.0 * alpha[None, :] * g + 5.0 * rng.standard_normal((N_CH, n))


def run(data, label):
    engine = DecoderEngine(Config.load(CFG))
    labels, confs = [], []
    for start in range(0, data.shape[1], CHUNK):
        block = data[:, start:start + CHUNK]
        if block.shape[1] == 0:
            continue
        for o in engine.push(EEGChunk(data=block, sfreq=SFREQ, t0=start / SFREQ, ch_names=NAMES)):
            labels.append(o.label); confs.append(o.confidence)
    from collections import Counter
    print(f"[{label}] 决策={len(labels)} 计数={dict(Counter(labels))} conf均值={float(np.mean(confs)):.2f}")

for s, tag in [("pure_left", "pure LEFT"), ("pure_right", "pure RIGHT"), ("weak_right", "WEAK right"), ("split", "split L/R")]:
    run(gen(s), tag)
