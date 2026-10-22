"""
里程碑③ · BCI Competition IV 2a 离线评测骨架（10/22 预研版，未对外报任何准确率）。

用途：
  1) 打通「数据下载 → 读入 → 事件分段 → (CSP / Riemann) → LDA → OOD 域内检测 → 指标」整条离线回测链路；
  2) 里程碑③（11/10）正式 Kappa 数字在此脚本基础上跑完整 9 受试得到；
  3) 实测记录环境 / 下载 / 耗时等工程事实，供组长拍板 ③ 口径。

纪律（红线）：
  - 本脚本的输出只作工程自检，MVP 阶段不得对外报告任何准确率数字；
  - 真实数字须在里程碑③（moabb + BCI IV 2a，Kappa>0.3 口径）正式评测时公布；
  - 数据一律落在 D 盘（MNE_DATA = .deepworks/mne_data，不入库）。

运行（Windows PowerShell，须用 m3 venv，在仓库根）：
  $env:PYTHONPATH = "D:/校企合作项目/bci-decoder"
  .deepworks/venv_m3/Scripts/python.exe bci-decoder/scripts/m3/offline_eval_bci4_2a.py --subjects 1
  自检（不下载、合成信号、只验证代码路径）：... --quick
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path

import numpy as np

# —— D 盘数据目录（用户偏好：所有下载落 D 盘）——
_DEFAULT_MNE_DATA = Path(r"D:\校企合作项目\.deepworks\mne_data")


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(description="BCI-IV-2a 离线回测骨架")
    parser.add_argument(
        "--subjects",
        type=str,
        default="1",
        help="受试编号，逗号分隔，默认 '1'；全部 9 个：1,2,3,4,5,6,7,8,9",
    )
    parser.add_argument(
        "--pipeline",
        choices=["csp", "riemann"],
        default="csp",
        help="特征路线：csp（对齐 MVP）或 riemann（④备用）",
    )
    parser.add_argument(
        "--quick",
        action="store_true",
        help="自检模式：用合成信号跑通代码路径，不下载真实数据",
    )
    parser.add_argument(
        "--with-ood",
        action="store_true",
        help="在特征域上拟合 OODDetector，验证其对不可见域样本的 idle 兜底链路",
    )
    parser.add_argument(
        "--load-only",
        action="store_true",
        help="只下载并读入数据、验证 shape 后退出，不跑回测（下载链路自检）",
    )
    parser.add_argument(
        "--mne-data",
        type=str,
        default=str(_DEFAULT_MNE_DATA),
        help="MNE_DATA 数据目录（默认 D 盘）",
    )
    args = parser.parse_args()

    os.environ["MNE_DATA"] = args.mne_data
    Path(args.mne_data).mkdir(parents=True, exist_ok=True)

    subjects = [int(s) for s in args.subjects.split(",")]
    print(f"[m3] MNE_DATA = {args.mne_data}")
    print(f"[m3] subjects = {subjects} | pipeline = {args.pipeline} | quick = {args.quick}")

    if args.quick:
        return _quick_selfcheck(args)

    from moabb.datasets import BNCI2014_001
    from moabb.paradigms import MotorImagery  # 标准 4 类（left/right/foot/tongue）

    dataset = BNCI2014_001()
    paradigm = MotorImagery(
        events=["left_hand", "right_hand", "feet", "tongue"], n_classes=4
    )
    print(f"[m3] 数据集: {dataset.code} | 事件: {dataset.event_id}")
    print(f"[m3] 开始下载/加载（数据落在 D 盘 {args.mne_data}）...")
    t0 = time.time()
    X, y, meta = paradigm.get_data(dataset, subjects=subjects)  # 内部触发下载
    print(
        f"[m3] 加载完成 | X={X.shape} y={y.shape} | 用时 {time.time()-t0:.1f}s"
    )
    print(
        f"[m3] meta subjects={sorted(set(meta['subject']))} "
        f"sessions={sorted(set(meta['session']))}"
    )

    if args.load_only:
        print(f"[m3] load-only：X={X.shape} y={y.shape} 读入成功，退出（不跑回测）")
        return 0

    from sklearn.model_selection import StratifiedKFold
    from sklearn.pipeline import make_pipeline
    from sklearn.discriminant_analysis import LinearDiscriminantAnalysis as LDA
    from sklearn.metrics import cohen_kappa_score, confusion_matrix, accuracy_score
    from sklearn.base import clone

    if args.pipeline == "riemann":
        from pyriemann.estimation import Covariances
        from pyriemann.tangentspace import TangentSpace

        pipeline = make_pipeline(Covariances(), TangentSpace(), LDA(solver="lsqr", shrinkage="auto"))
    else:
        from mne.decoding import CSP

        # 对齐 MVP：CSP(log=True) + LDA
        pipeline = make_pipeline(CSP(n_components=4, log=True, reg=None), LDA(solver="lsqr", shrinkage="auto"))

    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
    t1 = time.time()
    y_pred_all: list[int] = []
    y_true_all: list[int] = []
    for tr, te in cv.split(X, y):
        clf = clone(pipeline).fit(X[tr], y[tr])
        y_pred_all.extend(clf.predict(X[te]))
        y_true_all.extend(y[te])
    kappa = cohen_kappa_score(y_true_all, y_pred_all)
    acc = accuracy_score(y_true_all, y_pred_all)
    cm = confusion_matrix(y_true_all, y_pred_all)
    print(f"[m3] 5-fold | acc={acc:.3f} kappa={kappa:.3f}")
    print(f"[m3] confusion matrix (rows=true, cols=pred):\n{cm}")

    # —— OOD 域内检测（对齐 MVP 已落地的 OODDetector 口径）——
    if args.with_ood:
        from pyriemann.estimation import Covariances
        from bci_decoder.pipeline.ood import OODDetector  # 复用 MVP 实现

        # 说明：离线态 OOD 应在"训练折"特征上拟合、在"测试折"上生效；
        # 骨架先对整个特征集拟合以验证链路，正式版按折拟合。
        pipeline.fit(X, y)  # OOD 特征统一由全量拟合取得（正式版改为按折拟合 + idle 兜底评测）
        if args.pipeline == "riemann":
            feat = pipeline[:-1].transform(X)
        else:
            feat = pipeline[:-1].transform(X)
        ood = OODDetector(
            method="mahalanobis",
            chi2_quantile=0.99,
            score_scale=1.0,
            strength_floor_enabled=False,  # 离线骨架先只用马氏判据；strength 口径与在线一致，正式版再开
        )
        ood.fit(feat)
        outside = np.array([ood.is_outside(f) for f in feat])
        print(
            f"[m3] OOD 域内检出率 on training features: {outside.mean():.3f} "
            f"(期望≈0 域内不误杀，自检)"
        )
        print("[m3] OODDetector 链路 OK（正式版按折拟合 + 评测 idle 兜底）")

    print(f"[m3] 回测总耗时 {time.time()-t1:.1f}s（不含下载）")
    return 0


def _quick_selfcheck(args) -> int:
    """自检：合成 Epochs 跑通整条代码路径，绝不对外报告正确率数字。"""
    import numpy as np
    import mne
    from sklearn.model_selection import StratifiedKFold
    from sklearn.pipeline import make_pipeline
    from sklearn.discriminant_analysis import LinearDiscriminantAnalysis as LDA

    sfreq = 250.0
    n_trials, n_ch, n_t = 24, 22, 500
    rng = np.random.default_rng(0)
    ch_names = [f"EEG{i:03d}" for i in range(n_ch)]
    info = mne.create_info(ch_names, sfreq, "eeg")
    X = rng.standard_normal((n_trials, n_ch, n_t)) * 20.0
    y = np.array([0, 1] * (n_trials // 2))
    tt = np.arange(n_t)
    for i, yi in enumerate(y):
        if yi == 0:
            X[i, 18] += 90.0 * np.sin(2 * np.pi * 10 * tt / sfreq)
        else:
            X[i, 19] += 90.0 * np.sin(2 * np.pi * 10 * tt / sfreq)
    events = np.c_[
        np.arange(n_trials), np.zeros(n_trials, int), np.ones(n_trials, int)
    ]
    epochs = mne.EpochsArray(X, info, events)
    print(
        f"[m3][quick] 合成 Epochs: X={epochs.get_data().shape} "
        f"(仅工程自检，不构成任何准确率)"
    )

    if args.pipeline == "riemann":
        from pyriemann.estimation import Covariances
        from pyriemann.tangentspace import TangentSpace

        pipe = make_pipeline(Covariances(), TangentSpace(), LDA(solver="lsqr", shrinkage="auto"))
    else:
        from mne.decoding import CSP

        pipe = make_pipeline(CSP(n_components=4, log=True, reg=None), LDA(solver="lsqr", shrinkage="auto"))

    pipe.fit(X, y)  # 只验证代码路径，杜绝对外报数
    print("[m3][quick] CSP/riemann+LDA 拟合 OK（自检通过，数字不出现在任何报告）")

    if args.with_ood:
        from bci_decoder.pipeline.ood import OODDetector

        if args.pipeline == "riemann":
            from pyriemann.estimation import Covariances

            feat = pipe[0].fit_transform(X)
        else:
            feat = pipe[0].transform(X)
        ood = OODDetector(
            method="mahalanobis",
            chi2_quantile=0.99,
            score_scale=1.0,
            strength_floor_enabled=False,  # 离线骨架先只用马氏判据；strength 口径与在线一致，正式版再开
        )
        ood.fit(feat)
        outside = np.array([ood.is_outside(f) for f in feat])
        print(f"[m3][quick] OODDetector self-check: outside rate={outside.mean():.3f}")

    print("[m3][quick] 骨架自检完成 OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
