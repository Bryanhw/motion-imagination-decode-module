"""配置模型：一个实例的所有可调参数都集中在这里，便于交付与复现。

用法：
    cfg = Config.load("configs/default.yaml")
"""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass, field
from typing import Dict, List

DEFAULT_CH_NAMES = ["C3", "Cz", "C4", "CP3", "CP4", "P3", "P4", "Oz"]


@dataclass
class SourceConfig:
    kind: str = "mock"                 # mock | replay | lsl
    sfreq: float = 250.0
    ch_names: List[str] = field(default_factory=lambda: list(DEFAULT_CH_NAMES))
    chunk_samples: int = 25            # 每个数据块的样本数（250Hz * 0.1s）
    realtime: bool = True              # 是否按真实时间节流
    seed: int = 0                      # mock 源随机种子
    path: str = ""                     # replay 源的数据文件 (.npy, 形状 (n_ch, n_t))
    speed: float = 1.0                 # replay 源倍速
    loop: bool = False                 # replay 源是否循环
    stream_name: str = "BCI-EEG"       # lsl 源的流名称
    resolve_timeout: float = 5.0       # lsl 源查找流的超时（秒）


@dataclass
class PreprocessConfig:
    l_freq: float = 8.0
    h_freq: float = 30.0
    notch_freq: float = 50.0
    notch_q: float = 30.0
    filter_order: int = 4
    car: bool = True                   # 共平均参考
    artifact_ptp_uv: float = 200.0     # 峰峰值阈值（µV），超过则本窗口标记为脏


@dataclass
class FeatureConfig:
    kind: str = "bandpower"            # csp(当前路线) | bandpower(旧默认) | covariance(备用)
    bands: Dict[str, List[float]] = field(
        default_factory=lambda: {"mu": [8.0, 13.0], "beta": [13.0, 30.0]}
    )
    covariance_shrinkage: float = 0.1
    # ---- CSP（当前技术路线，见 docs/详细技术路线.md）----
    csp_components: int = 4            # 空间滤波器个数（2 对）→ 特征维数 = csp_components
    csp_reg: float = 1e-4              # 平均协方差的收缩正则，增强数值稳定
    model_path: str = ""               # 训练好的 CSP 模型路径（含空间滤波矩阵 W）


@dataclass
class ClassifierConfig:
    kind: str = "lda"                  # lda | onnx | untrained
    classes: List[str] = field(default_factory=lambda: ["left", "right"])
    model_path: str = ""               # 训练好的模型路径 (.joblib)
    onnx_path: str = ""                # onnx 模型路径


@dataclass
class PostprocessConfig:
    vote_window: int = 3               # 连续 N 次一致才切换输出
    ema_alpha: float = 0.4             # 概率指数平滑系数
    min_confidence: float = 0.6        # 低于此置信度则输出 idle
    idle_label: str = "idle"


@dataclass
class WindowConfig:
    window_seconds: float = 2.0        # 滑动窗长度
    step_seconds: float = 0.25         # 决策步长


@dataclass
class OutputConfig:
    sinks: List[str] = field(default_factory=lambda: ["console"])
    record_path: str = ""              # JSONL 记录路径（留空则不记录）
    ws_host: str = "127.0.0.1"
    ws_port: int = 8765


@dataclass
class Config:
    source: SourceConfig = field(default_factory=SourceConfig)
    preprocess: PreprocessConfig = field(default_factory=PreprocessConfig)
    features: FeatureConfig = field(default_factory=FeatureConfig)
    classifier: ClassifierConfig = field(default_factory=ClassifierConfig)
    postprocess: PostprocessConfig = field(default_factory=PostprocessConfig)
    window: WindowConfig = field(default_factory=WindowConfig)
    output: OutputConfig = field(default_factory=OutputConfig)

    # ---- 派生量 ----
    def window_samples(self) -> int:
        return max(1, int(round(self.window.window_seconds * self.source.sfreq)))

    def step_samples(self) -> int:
        return max(1, int(round(self.window.step_seconds * self.source.sfreq)))

    # ---- 读写 ----
    @classmethod
    def from_dict(cls, raw: dict) -> "Config":
        raw = raw or {}

        def sub(tp, key):
            data = raw.get(key) or {}
            valid = {f.name for f in dataclasses.fields(tp)}
            return tp(**{k: v for k, v in data.items() if k in valid})

        return cls(
            source=sub(SourceConfig, "source"),
            preprocess=sub(PreprocessConfig, "preprocess"),
            features=sub(FeatureConfig, "features"),
            classifier=sub(ClassifierConfig, "classifier"),
            postprocess=sub(PostprocessConfig, "postprocess"),
            window=sub(WindowConfig, "window"),
            output=sub(OutputConfig, "output"),
        )

    @classmethod
    def load(cls, path: str) -> "Config":
        import yaml

        with open(path, "r", encoding="utf-8") as f:
            raw = yaml.safe_load(f)
        return cls.from_dict(raw)

    def to_dict(self) -> dict:
        return dataclasses.asdict(self)

    def save(self, path: str) -> None:
        import yaml

        with open(path, "w", encoding="utf-8") as f:
            yaml.safe_dump(self.to_dict(), f, allow_unicode=True, sort_keys=False)
