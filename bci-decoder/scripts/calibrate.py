"""校准流程骨架脚本：为新用户（subject）训练专属模型并产出可直接运行的配置。

设计意图（对应 docs/calibration_flow.md）：
- 复用 bootstrap_demo 已有的 "trial → 预处理 → 特征 → LDA → 保存" 链路，不重造轮子；
- 按 <subject_id> 分目录组织产物，天然对接冻结契约里的 load_subject；
- 里程碑②（MVP）用 synth 数据占位做工程自检；里程碑④ 接入真实采集数据只需传
  --real-data / --labels，脚本逻辑不变。

用法（在 bci-decoder 目录下）：
    python scripts/calibrate.py --subject-id demo                # synth 自检
    python scripts/calibrate.py --subject-id alice --real-data data/alice.npy --labels data/alice_labels.npy

产出：
    artifacts/users/<subject_id>/classifier.joblib    # LDA
    artifacts/users/<subject_id>/csp.joblib           # CSP 空间滤波（kind=csp 时）
    artifacts/users/<subject_id>/online.yaml          # 可直接被 cli run 加载
    artifacts/users/<subject_id>/metadata.json        # 来源/规模记录（不含准确率）

红线遵守：
- mock/synth 数据只用于工程自检，不对外报告准确率（本脚本只打印 CV 参考值并提示）。
- 通道顺序即语义：真实数据通道顺序必须与来源配置一致，脚本不重排。
"""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # 便于 import bootstrap_demo

from bci_decoder.config import Config  # noqa: E402
from bci_decoder.pipeline.classifier import LDAClassifier  # noqa: E402
from bci_decoder.pipeline.features import CSPExtractor  # noqa: E402
import bootstrap_demo  # noqa: E402


DEFAULT_USERS_ROOT = os.path.join("artifacts", "users")


class CalibrationResult:
    """一次校准的产物路径集合与基本信息。"""

    def __init__(self, subject_id: str, root: str):
        self.subject_id = subject_id
        self.root = root
        self.clf_path = os.path.join(root, "classifier.joblib")
        self.csp_path = os.path.join(root, "csp.joblib")
        self.cfg_path = os.path.join(root, "online.yaml")
        self.meta_path = os.path.join(root, "metadata.json")


def _load_or_default(args) -> Config:
    if os.path.exists(args.config):
        return Config.load(args.config)
    return Config()


def _prepare_trials(args, cfg: Config):
    """数据来源：真实采集（--real-data）或 synth 自检占位。

    返回 (trials: list[np.ndarray]，labels: np.ndarray，source: str)。
    trial 形状 (n_ch, n_samples)，与 bootstrap_demo 的切分逻辑保持一致。
    """
    if args.real_data and args.labels:
        raw = np.load(args.real_data)
        labels = np.load(args.labels)
        step = int(cfg.source.sfreq * args.trial_seconds)
        if raw.shape[1] < len(labels) * step:
            raise ValueError(
                f"真实数据长度不足：raw.shape={raw.shape}，labels 数={len(labels)}，"
                f"需要至少 {len(labels) * step} 样本。"
            )
        trials = [raw[:, i * step : (i + 1) * step] for i in range(len(labels))]
        print(f"[calibrate] 数据来源=真实采集：{len(trials)} 个 trial")
        return trials, labels, "real"
    trials, labels = bootstrap_demo.synthesize_dataset(
        n_per_class=args.n_per_class,
        sfreq=cfg.source.sfreq,
        ch_names=cfg.source.ch_names,
        seconds=args.trial_seconds,
        seed=cfg.source.seed,
    )
    print(f"[calibrate] 数据来源=synth 自检占位：{len(trials)} 个 trial（仅工程自检，不对外报准确率）")
    return trials, labels, "synth"


def _write_user_config(cfg: Config, clf_path: str, csp_path: str, out_path: str) -> None:
    """基于基础配置，把 model_path 指向该用户产物，产出 online.yaml（相对路径解析自 bci-decoder 运行目录）。"""
    import copy

    c = copy.deepcopy(cfg)
    c.classifier.model_path = clf_path.replace("\\", "/")
    if getattr(c.features, "kind", "") == "csp":
        c.features.model_path = csp_path.replace("\\", "/")
    c.save(out_path)


def main() -> int:
    ap = argparse.ArgumentParser(description="校准流程骨架（生成用户专属模型与可运行配置）")
    ap.add_argument("--subject-id", default="demo", help="用户 ID（决定 artifacts/users/<id>/ 目录名）")
    ap.add_argument("--config", default="configs/default.yaml", help="基础配置")
    ap.add_argument("--real-data", default="", help="真实采集 .npy (n_ch, n_t)，需配 --labels")
    ap.add_argument("--labels", default="", help="标签 .npy，长度=trial 数")
    ap.add_argument("--n-per-class", type=int, default=20, help="synth 自检时每类 trial 数（默认 20，对应规格书 20–30）")
    ap.add_argument("--trial-seconds", type=float, default=2.0, help="trial 时长（默认 2.0s，与滑窗一致）")
    ap.add_argument("--out-dir", default=DEFAULT_USERS_ROOT, help="用户模型根目录（默认 artifacts/users）")
    args = ap.parse_args()

    cfg = _load_or_default(args)
    root = os.path.join(args.out_dir, args.subject_id)
    os.makedirs(root, exist_ok=True)
    res = CalibrationResult(args.subject_id, root)

    # 1) 取数据（真实采集 or synth 占位）
    trials, labels, source = _prepare_trials(args, cfg)

    # 2) 训练特征提取器 + 提取特征（复用 bootstrap_demo，保证训练/推理一致）
    x, extractor = bootstrap_demo.extract_features(trials, cfg, labels)
    print(f"[calibrate] 特征维度：{x.shape}（CSP W 已随特征提取器训练/加载）")

    # 3) 工程自检：交叉验证（仅供确认数据可分，非性能分，不对外报）
    from sklearn.discriminant_analysis import LinearDiscriminantAnalysis
    from sklearn.model_selection import cross_val_score
    from sklearn.pipeline import Pipeline
    from sklearn.preprocessing import StandardScaler

    pipe = Pipeline([("scaler", StandardScaler()), ("lda", LinearDiscriminantAnalysis())])
    try:
        scores = cross_val_score(pipe, x, labels, cv=5)
        print(
            f"[calibrate] [工程自检] 5 折 CV 均值={scores.mean():.3f}  "
            "（仅确认链路可分性，禁止对外报告准确率）"
        )
    except Exception as exc:  # 骨架阶段允许采集不足导致 CV 失败，仅告警不中断
        print(f"[calibrate] [告警] 交叉验证不可用（{exc}），跳过工程自检")

    # 4) 训练并保存 LDA
    clf = LDAClassifier().fit(x, labels)
    clf.save(res.clf_path)
    print(f"[calibrate] 模型已保存：{res.clf_path}")

    # 5) 保存 CSP 空间滤波（kind=csp 时）
    if isinstance(extractor, CSPExtractor):
        extractor.save(res.csp_path)
        print(f"[calibrate] CSP 空间滤波已保存：{res.csp_path}")

    # 6) 产出可运行配置（model_path 指向本用户产物）
    _write_user_config(cfg, res.clf_path, res.csp_path, res.cfg_path)
    print(f"[calibrate] 已生成可运行配置：{res.cfg_path}")

    # 7) 元信息（不含准确率）
    meta = {
        "subject_id": args.subject_id,
        "created_utc": _dt.datetime.now(_dt.timezone.utc).isoformat(),
        "source": source,
        "n_trials": int(len(labels)),
        "n_features": int(x.shape[1]),
        "classes": list(cfg.classifier.classes),
        "config": args.config,
        "files": {
            "classifier": res.clf_path.replace("\\", "/"),
            "csp": (res.csp_path.replace("\\", "/") if isinstance(extractor, CSPExtractor) else None),
            "online_yaml": res.cfg_path.replace("\\", "/"),
        },
    }
    with open(res.meta_path, "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)
    print(f"[calibrate] 元信息已保存：{res.meta_path}")

    print("\n下一步（启动在线解码，使用本用户模型）：")
    print(f"    python -m bci_decoder.cli run --config {res.cfg_path}")
    print("若数据来自真实采集：请按 docs/calibration_flow.md §5 走质量门（试玩门属里程碑④）。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
