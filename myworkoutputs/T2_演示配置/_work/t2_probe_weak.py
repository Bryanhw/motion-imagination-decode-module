# 弱信号形态探测（T2c 工程自检）：枚举候选数据 → engine.push → 比较 label/conf 分布
from __future__ import annotations
import os
import sys
import numpy as np

os.chdir(r"D:\校企合作项目\bci-decoder")
sys.path.insert(0, r"D:\校企合作项目\bci-decoder")
from bci_decoder.config import Config
from bci_decoder.core import DecoderEngine
from bci_decoder.types import EEGChunk

CFG = r"D:\校企合作项目\bci-decoder\configs\demo_weak.yaml"
SFREQ = 250.0
N_CH = 8
SECONDS = 40.0
CHUNK = 25
NAMES = ["C3", "Cz", "C4", "CP3", "CP4", "P3", "P4", "Oz"]


def gen(kind: str):
    n = int(SFREQ * SECONDS)
    rng = np.random.default_rng(7)
    t = np.arange(n) / SFREQ
    alpha = np.sin(2 * np.pi * 10.0 * t)
    if kind == "A_noise25":
        return 25.0 * rng.standard_normal((N_CH, n))
    if kind == "B_noise6":
        return 6.0 * rng.standard_normal((N_CH, n))
    if kind == "C_commonsource":
        return 15.0 * alpha[None, :] + 5.0 * rng.standard_normal((N_CH, n))
    if kind == "D_mix025":
        lab = ((t // 0.25) % 2).astype(int)
        g = np.ones((N_CH, n))
        g[0] = 1.0 + 0.8 * (1 - lab)
        g[2] = 1.0 + 0.8 * lab
        return 12.0 * alpha[None, :] * g + 6.0 * rng.standard_normal((N_CH, n))
    if kind == "E_mix025_hi":
        lab = ((t // 0.25) % 2).astype(int)
        g = np.ones((N_CH, n))
        g[0] = 1.0 + 0.8 * (1 - lab)
        g[2] = 1.0 + 0.8 * lab
        return 12.0 * alpha[None, :] * g + 25.0 * rng.standard_normal((N_CH, n))
    raise ValueError(kind)


for kind in ["A_noise25", "B_noise6", "C_commonsource", "D_mix025", "E_mix025_hi"]:
    data = gen(kind)
    engine = DecoderEngine(Config.load(CFG))
    labels, confs = [], []
    for start in range(0, data.shape[1], CHUNK):
        block = data[:, start:start + CHUNK]
        if block.shape[1] == 0:
            continue
        outs = engine.push(EEGChunk(data=block, sfreq=SFREQ, t0=start / SFREQ, ch_names=NAMES))
        for o in outs:
            labels.append(o.label)
            confs.append(o.confidence)
    from collections import Counter
    print(f"[{kind}] 决策={len(labels)} 计数={dict(Counter(labels))} conf均值={float(np.mean(confs)):.2f} conf范围=[{float(np.min(confs)):.2f},{float(np.max(confs)):.2f}]")
