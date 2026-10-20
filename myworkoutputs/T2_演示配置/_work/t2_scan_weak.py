# 弱信号参数扫描：找“稳定全 idle”的合成设计（T2c 工程自检）
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


def gen(amp, noise, style):
    n = int(SFREQ * SECONDS)
    rng = np.random.default_rng(11)
    t = np.arange(n) / SFREQ
    alpha = np.sin(2 * np.pi * 10.0 * t)
    if style == "alt4":
        lab = ((t // 4.0) % 2).astype(int)
    elif style == "alt0.5":
        lab = ((t // 0.5) % 2).astype(int)
    else:
        lab = ((t // 0.25) % 2).astype(int)
    g = np.ones((N_CH, n))
    g[0] = 1.0 + 0.8 * (1 - lab)
    g[2] = 1.0 + 0.8 * lab
    return amp * alpha[None, :] * g + noise * rng.standard_normal((N_CH, n))


engine = DecoderEngine(Config.load(CFG))
for amp in [0.5, 1.0, 2.0]:
    for noise in [15.0, 25.0]:
        for style in ["alt4", "alt0.5", "alt0.25"]:
            data = gen(amp, noise, style)
            # 复用同一 engine? 不行，状态会污染，每个 combo 新建（并重置稳定器）
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
            print(f"amp={amp:>4} noise={noise:>4} {style} -> n={len(labels)} idle={idle_ratio*100:5.1f}% 计数={dict(cnt)}")
