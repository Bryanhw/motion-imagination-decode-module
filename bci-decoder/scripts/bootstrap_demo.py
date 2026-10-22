"""端到端自检脚本：验证"数据 → 特征 → 模型 → 在线解码"整条链路是否贯通。

它做四件事：
1. 生成合成 trial（无真实数据时也能跑）
2. 用与在线完全一致的预处理 + 特征提取（保证训练/推理一致性）
3. 训练 LDA 并做交叉验证
4. 保存模型，供 cli run 加载后做在线解码

用法（在 bci-decoder 目录下执行）：
    python scripts/bootstrap_demo.py
    python scripts/bootstrap_demo.py --real-data data/sub01.npy --sfreq 250
"""

from __future__ import annotations

import argparse
import json
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bci_decoder.config import Config, DEFAULT_CH_NAMES, PreprocessConfig  # noqa: E402
from bci_decoder.pipeline.classifier import LDAClassifier  # noqa: E402
from bci_decoder.pipeline.features import CSPExtractor, build_feature_extractor  # noqa: E402
from bci_decoder.pipeline.ood import OODDetector  # noqa: E402
from bci_decoder.pipeline.preprocess import Preprocessor  # noqa: E402
from bci_decoder.synth import synthesize_dataset  # noqa: E402


def extract_features(trials, cfg: Config, labels=None, return_strength: bool = False):
    """对每个 trial 独立跑一遍预处理+特征，模拟在线窗口。

    CSP 路线：CSP 是有状态特征，先用全部（预处理后的）窗口 fit 学到空间滤波矩阵 W，
    再逐个 transform；保证训练/推理完全一致。bandpower/covariance 无状态，直接逐 trial 提取。

    return_strength=True 时额外返回强度标量数组 (n,)，口径与 core.DecoderEngine._window_strength
    完全一致（跨通道 RMS，预处理后窗口），供域内检测器标定信号强度下限。
    """
    n_ch = len(cfg.source.ch_names)
    pre = Preprocessor(cfg.preprocess, n_ch, cfg.source.sfreq)
    # 训练阶段总是从零学习（忽略 config 里可能存在的已训练 model_path，改为不加载）
    import dataclasses

    fcfg = dataclasses.replace(cfg.features, model_path="")
    ex = build_feature_extractor(fcfg, cfg.source.sfreq)
    cleaned = []
    for tr in trials:
        clean, _ = pre.process(tr)
        cleaned.append(clean)
        pre.reset()          # trial 之间互相独立，重置滤波状态
    if isinstance(ex, CSPExtractor) and not ex.trained:
        ex.fit(np.stack(cleaned), np.asarray(labels))
    feats = np.asarray([ex.transform(c) for c in cleaned])
    if not return_strength:
        return feats, ex
    strengths = np.asarray(
        [np.sqrt(np.mean(np.var(c, axis=1))) for c in cleaned], dtype=np.float64
    )
    return feats, ex, strengths


def main() -> int:
    ap = argparse.ArgumentParser(description="解码链路端到端自检与模型训练")
    ap.add_argument("--config", default="configs/default.yaml")
    ap.add_argument("--n-per-class", type=int, default=40)
    ap.add_argument("--real-data", default="", help="真实数据 .npy (n_ch, n_t)，需配 --labels")
    ap.add_argument("--labels", default="", help="标签 .npy，长度等于 trial 数")
    ap.add_argument("--trial-seconds", type=float, default=2.0)
    ap.add_argument("--out", default="artifacts/demo_lda.joblib")
    ap.add_argument("--out-csp", default="artifacts/demo_csp.joblib",
                    help="CSP 空间滤波模型输出路径（kind=csp 时保存）")
    ap.add_argument("--out-ood", default="artifacts/ood.joblib",
                    help="域内检测器（OODDetector）输出路径；字段随 configs 的 ood 块决定")
    args = ap.parse_args()

    cfg = Config.load(args.config) if os.path.exists(args.config) else Config()
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)

    if args.real_data and args.labels:
        raw = np.load(args.real_data)
        labels = np.load(args.labels)
        step = int(cfg.source.sfreq * args.trial_seconds)
        trials = [raw[:, i * step:(i + 1) * step] for i in range(len(labels))]
        print(f"[bootstrap] 使用真实数据：{len(trials)} 个 trial")
    else:
        trials, labels = synthesize_dataset(
            n_per_class=args.n_per_class,
            sfreq=cfg.source.sfreq,
            ch_names=cfg.source.ch_names,
            seconds=args.trial_seconds,
            seed=cfg.source.seed,
        )
        print(f"[bootstrap] 使用合成自检数据：{len(trials)} 个 trial（不可用于性能评估）")

    x, extractor, strengths = extract_features(trials, cfg, labels, return_strength=True)
    print(f"[bootstrap] 特征维度：{x.shape}")

    # 交叉验证：看流水线是否真的携带可分信息
    from sklearn.discriminant_analysis import LinearDiscriminantAnalysis
    from sklearn.model_selection import cross_val_score
    from sklearn.pipeline import Pipeline
    from sklearn.preprocessing import StandardScaler

    pipe = Pipeline([("scaler", StandardScaler()), ("lda", LinearDiscriminantAnalysis())])
    scores = cross_val_score(pipe, x, labels, cv=5)
    print(f"[bootstrap] 5折交叉验证准确率：{scores.mean():.3f} ± {scores.std():.3f}")
    print("[bootstrap] 注意：上列数字来自合成数据自检（mock/synth），不是算法成绩，禁止对外报告准确率（红线 R-1）")

    clf = LDAClassifier().fit(x, labels)
    clf.save(args.out)
    print(f"[bootstrap] 模型已保存：{args.out}")

    if isinstance(extractor, CSPExtractor):
        extractor.save(args.out_csp)
        print(f"[bootstrap] CSP 空间滤波模型已保存：{args.out_csp}")

    # 域内检测器（2c 缺陷改进，D2 提案落地）：用训练特征/强度标定域分布，随模型产物发布
    ood = OODDetector(
        method=cfg.ood.method,
        chi2_quantile=cfg.ood.chi2_quantile,
        score_scale=cfg.ood.score_scale,
        strength_floor_enabled=cfg.ood.strength_floor_enabled,
    )
    ood.fit(x, strengths if cfg.ood.strength_floor_enabled else None)
    ood.save(args.out_ood)
    print(f"[bootstrap] 域内检测器已保存：{args.out_ood} "
          f"(method={ood.method}, strength_floor={ood.strength_floor_enabled})")
    print(f"[bootstrap] OOD 阈值：{ood.describe()}")
    print("[bootstrap] 注意：下方 cv_accuracy 同为合成数据自检值，仅用于确认流水线可跑通，不得作为性能指标")
    print(json.dumps({
        "n_trials": int(len(labels)),
        "n_features": int(x.shape[1]),
        "cv_accuracy": float(scores.mean()),
        "model_path": args.out,
        "ood_path": args.out_ood,
        "classes": cfg.classifier.classes,
    }, ensure_ascii=False, indent=2))
    print("\n下一步：把 configs/default.yaml 里的 classifier.model_path 指向该模型，")
    print("      再执行 python -m bci_decoder.cli run --config configs/default.yaml")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
