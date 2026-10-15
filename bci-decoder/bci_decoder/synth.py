"""合成带标签的脑电数据，用于在无真实数据时验证整条训练/解码链路。

生成的信号遵循运动想象最典型的 ERD/ERS 现象：
- label 0（想象左手）：C3 通道 alpha(10Hz) 功率增强
- label 1（想象右手）：C4 通道 alpha(10Hz) 功率增强

注意：这是**工程自检数据**，只用于验证代码链路是否正确，
绝不能用来评估算法性能或对外报告准确率。
"""

from __future__ import annotations

from typing import Sequence

import numpy as np


def synthesize_trial(
    label: int,
    sfreq: float = 250.0,
    ch_names: Sequence[str] = ("C3", "Cz", "C4"),
    seconds: float = 2.0,
    rng: np.random.Generator | None = None,
) -> np.ndarray:
    """生成一个类别的模拟 trial，返回 (n_channels, n_samples)，单位 µV。"""
    rng = rng or np.random.default_rng()
    names = list(ch_names)
    n_ch = len(names)
    n = int(round(sfreq * seconds))
    t = np.arange(n) / sfreq

    alpha = np.sin(2 * np.pi * 10.0 * t)
    gain = np.ones((n_ch, n), dtype=np.float64)

    if "C3" in names:
        gain[names.index("C3")] = 1.0 + 0.8 * (1 - int(label))
    if "C4" in names:
        gain[names.index("C4")] = 1.0 + 0.8 * int(label)

    data = 15.0 * alpha[None, :] * gain
    data += 5.0 * rng.standard_normal((n_ch, n))
    return data


def synthesize_dataset(
    n_per_class: int = 30,
    n_classes: int = 2,
    sfreq: float = 250.0,
    ch_names: Sequence[str] = ("C3", "Cz", "C4"),
    seconds: float = 2.0,
    seed: int = 0,
) -> tuple[list[np.ndarray], np.ndarray]:
    """生成平衡的两类 trial 列表与标签。"""
    rng = np.random.default_rng(seed)
    trials: list[np.ndarray] = []
    labels: list[int] = []
    for label in range(n_classes):
        for _ in range(n_per_class):
            trials.append(synthesize_trial(label, sfreq, ch_names, seconds, rng))
            labels.append(label)
    order = rng.permutation(len(trials))
    return [trials[i] for i in order], np.asarray([labels[i] for i in order])
