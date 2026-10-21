"""解码引擎：把数据源、流水线、输出通道串成一个在线闭环。

在线时序（每个 chunk 到达时执行）：

    chunk ──▶ 预处理(带状态滤波) ──▶ 环形缓冲
                                      │
                         每累积 step 个样本触发一次决策
                                      ▼
                         取最近 window 个样本 ──▶ 特征 ──▶ 分类 ──▶ 稳定化 ──▶ 输出

注意区分两种"延迟"：
- compute_ms：本次决策的纯计算耗时（滤波/特征/推理/平滑），工程上要求 < 50ms。
- window_seconds：滑窗长度，是端到端响应的主要成分（信息必须累积够才能判断）。
  游戏侧感受到的延迟 ≈ window_seconds + compute_ms，因此窗口长度要与游戏节奏共同确定。
"""

from __future__ import annotations

import os
import time
from typing import Iterable

import numpy as np

from .buffer import RingBuffer
from .config import Config
from .pipeline.classifier import build_classifier
from .pipeline.features import build_feature_extractor
from .pipeline.ood import OODDetector
from .pipeline.postprocess import DecisionStabilizer
from .pipeline.preprocess import Preprocessor
from .sources import Source, build_source
from .types import DecoderOutput, EEGChunk


class DecoderEngine:
    """在线运动想象解码引擎。"""

    def __init__(self, cfg: Config, classifier=None):
        self.cfg = cfg
        self.n_channels = len(cfg.source.ch_names)
        self.sfreq = float(cfg.source.sfreq)
        self.window_samples = cfg.window_samples()
        self.step_samples = cfg.step_samples()

        capacity = int(self.window_samples * 4 + self.sfreq)
        self.buffer = RingBuffer(self.n_channels, capacity, self.sfreq)
        self.pre = Preprocessor(cfg.preprocess, self.n_channels, self.sfreq)
        self.features = build_feature_extractor(cfg.features, self.sfreq)
        self.classifier = classifier if classifier is not None else build_classifier(cfg.classifier)
        self.stabilizer = DecisionStabilizer(cfg.postprocess)
        self.class_names = list(cfg.classifier.classes)
        self.ood = self._build_ood(cfg.ood)

        self._since_last = 0
        self.compute_times_ms: list[float] = []
        self.n_outputs = 0

    # ---- 域内检测（OOD，默认关，灰度开） ----
    @staticmethod
    def _build_ood(occfg) -> OODDetector | None:
        """按配置加载域内检测器；开启但模型缺失/加载失败时优雅降级为不启用。"""
        if not getattr(occfg, "enabled", False):
            return None
        if not occfg.model_path or not os.path.exists(occfg.model_path):
            print(f"[bci-decoder] ⚠️ ood.enabled=True 但未找到 model_path={occfg.model_path!r}，OOD 未启用")
            return None
        try:
            det = OODDetector.load(occfg.model_path)
            print(f"[bci-decoder] OOD 域内检测已启用：{occfg.model_path} "
                  f"(method={det.method}, strength_floor={det.strength_floor_enabled})")
            return det
        except Exception as e:  # pragma: no cover
            print(f"[bci-decoder] ⚠️ OOD 模型加载失败，降级为不启用：{e}")
            return None

    @staticmethod
    def _window_strength(x: np.ndarray) -> float:
        """在线窗口强度标量（µV）：跨通道 RMS 幅值。训练/在线必须同口径。"""
        x = np.asarray(x, dtype=np.float64)
        return float(np.sqrt(np.mean(np.var(x, axis=1))))

    # ---- 单次推进 ----
    def push(self, chunk: EEGChunk) -> list[DecoderOutput]:
        """送入一个数据块，返回本次触发的所有解码结果（可能 0 个或多个）。"""
        clean_data, is_clean = self.pre.process(chunk.data)
        self.buffer.append(clean_data, chunk.t0)

        outputs: list[DecoderOutput] = []
        self._since_last += int(clean_data.shape[1])

        while self.buffer.total >= self.window_samples and self._since_last >= self.step_samples:
            self._since_last -= self.step_samples
            t_start = time.perf_counter()

            window = self.buffer.get_last(self.window_samples)
            feat = self.features.transform(window)
            if self.ood is not None:
                strength = self._window_strength(window) if self.ood.strength_floor_enabled else None
                ood = self.ood.is_outside(feat, strength)
            else:
                ood = False
            if ood:
                # 域外：喂均匀概率给稳定器，自然走 idle（9 字段契约零改动）
                probs = np.full(len(self.class_names), 1.0 / len(self.class_names))
            else:
                probs = self.classifier.predict_proba(feat)
            label, conf = self.stabilizer.update(probs, self.class_names)

            compute_ms = (time.perf_counter() - t_start) * 1000.0
            self.compute_times_ms.append(compute_ms)
            self.n_outputs += 1

            label_id = self.class_names.index(label) if label in self.class_names else -1
            state = "running" if is_clean and label != self.cfg.postprocess.idle_label else (
                "stabilizing" if not is_clean else "running"
            )

            outputs.append(
                DecoderOutput(
                    t_data=self.buffer.latest_time(),
                    t_wall=time.perf_counter(),
                    label=label,
                    label_id=label_id,
                    confidence=conf,
                    probs=np.asarray(probs, dtype=float).tolist(),
                    state=state,
                    compute_ms=compute_ms,
                    window_seconds=self.cfg.window.window_seconds,
                )
            )
        return outputs

    # ---- 主循环 ----
    def run(self, source: Source | None = None, sinks: Iterable = (), max_chunks: int | None = None) -> None:
        """持续运行解码循环。max_chunks 用于测试时限制运行长度。"""
        src = source or build_source(self.cfg.source)
        sink_list = list(sinks)
        n = 0
        try:
            src.start()
            for chunk in src.stream():
                for out in self.push(chunk):
                    for sink in sink_list:
                        sink.emit(out)
                n += 1
                if max_chunks is not None and n >= max_chunks:
                    break
        finally:
            src.stop()
            for sink in sink_list:
                sink.close()

    # ---- 统计 ----
    def latency_report(self) -> dict:
        if not self.compute_times_ms:
            return {"n": 0}
        arr = np.asarray(self.compute_times_ms)
        return {
            "n": int(arr.size),
            "mean_ms": float(arr.mean()),
            "p50_ms": float(np.percentile(arr, 50)),
            "p95_ms": float(np.percentile(arr, 95)),
            "max_ms": float(arr.max()),
            "window_seconds": self.cfg.window.window_seconds,
            "est_e2e_p95_ms": float(np.percentile(arr, 95) + self.cfg.window.window_seconds * 1000),
        }
