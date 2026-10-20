# 弱信号扫描2：持续单侧极弱结构 → 能否稳定 idle（T2c 工程自检）
from __future__ import annotations
import os, sys
import numpy as np
from collections import Counter

os.chdir(r"D:\校企合作项目\bci-decoder")
sys.path.insert(0, r"D:\校企合作项目\bci-decoder")
from bci_decoder.config import Config
from bci_decoder.core import DecoderEngine
from bci_decoder.types import EEGChunk

CFG = r"D:\校企合作项目\bci-decoder\configs\demo_weak.yaml"
SFREQ, N_CH, SECONDS, CHUNK = 250.0, 8, 20.0, 25
NAMES = ["C3", "Cz", "C4", "CP3", "CP4", "P3", "P4", "Oz"]


def run_cfg(amp, beta, noise):
    n = int(SFREQ * SECONDS)
    rng = np.random.default_rng(13)
    t = np.arange(n) / SFREQ
    alpha = np.sin(2 * np.pi * 10.0 * t)
    g = np.ones((N_CH, n))
    g[0] = 1.0 + beta
    g[2] = 1.0 - beta  # 持续 C4 略弱于 C3（单侧弱结构）
    data = amp * alpha[None, :] * g + noise * rng.standard_normal((N_CH, n))
    e = DecoderEngine(Config.load(CFG))
    labels = []
    for start in range(0, data.shape[1], CHUNK):
        block = data[:, start:start + CHUNK]
        if block.shape[1] == 0:
            continue
        for o in e.push(EEGChunk(data=block, sfreq=SFREQ, t0=start / SFREQ, ch_names=NAMES)):
            labels.append(o.label)
    cnt = Counter(labels)
    idle_ratio = cnt.get("idle", 0) / max(1, len(labels))
    print(f"amp={amp:>4} beta={beta:>4} noise={noise:>4} -> n={len(labels)} idle={idle_ratio*100:5.1f}% 计数={dict(cnt)}")

for amp in [0.5, 1.0]:
    for beta in [0.01, 0.02, 0.05, 0.1, 0.2]:
        run_cfg(amp, beta, 25.0)
