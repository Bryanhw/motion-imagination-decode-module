"""决策后处理：把逐次波动的分类输出变成游戏可用的稳定指令。

设计原则：**宁可迟钝，不可抖动**。
游戏里频繁误切方向比偶尔慢半拍更让用户挫败。
"""

from __future__ import annotations

from collections import deque

import numpy as np

from ..config import PostprocessConfig


class DecisionStabilizer:
    """指数平滑 + 连续一致性投票 + 置信度门限。"""

    def __init__(self, cfg: PostprocessConfig):
        self.cfg = cfg
        self.vote_window = max(1, int(cfg.vote_window))
        self.idle_label = cfg.idle_label
        self._ema: np.ndarray | None = None
        self._votes: deque[int] = deque(maxlen=self.vote_window)
        self._current: str = cfg.idle_label

    def update(self, probs: np.ndarray, class_names: list[str]) -> tuple[str, float]:
        """输入本次分类概率，返回稳定后的 (label, confidence)。"""
        probs = np.asarray(probs, dtype=np.float64).ravel()

        # 1) 概率指数平滑，抑制单次抖动
        if self._ema is None or self._ema.shape != probs.shape:
            self._ema = probs.copy()
        else:
            a = self.cfg.ema_alpha
            self._ema = a * probs + (1.0 - a) * self._ema
        # 归一化，防止数值漂移
        total = self._ema.sum()
        if total > 0:
            self._ema = self._ema / total

        top = int(np.argmax(self._ema))
        conf = float(self._ema[top])

        # 2) 连续一致性投票
        self._votes.append(top)
        stable = len(self._votes) == self.vote_window and len(set(self._votes)) == 1

        if not stable:
            # 尚在抖动中：保持上一次输出，避免频繁切换
            return self._current, conf

        # 3) 置信度门限：不够自信就退回 idle
        if conf < self.cfg.min_confidence:
            self._current = self.idle_label
        else:
            self._current = class_names[top] if top < len(class_names) else self.idle_label
        return self._current, conf

    def reset(self) -> None:
        self._ema = None
        self._votes.clear()
        self._current = self.cfg.idle_label
