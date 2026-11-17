# -*- coding: utf-8 -*-
"""M4 D1: 个人校准 vs 免校准 — BCI Competition IV 2a（9 受试，内部工程记录）。

口径（依组长 2026-11-16..22 团队任务总表 D1 / 阎浩文本周任务卡）：
  - 数据：BNCI2014-001（BCI IV 2a），2 类 left/right，22 真实通道；
  - 预处理：完全沿用 M3（notch50 + bp8-30(4) + CAR，窗 2.0s/步 0.5s，从 cue 后 250 点起）；
  - 免校准（对照）：其余 8 人 0train 训练 → 测留出人 1test（即 M3 LOO 口径复用，预期≈0.19）；
  - 个人校准（实验组）：留出人自己 0train 前 N trial/类 训练个人 CSP+LDA → 测同一 1test；
  - 校准梯度：N = 10 / 20 / 30（每类 trial 数，约 2 / 4 / 6 分钟）；
  - ***防泄漏铁律***：校准只用 0train 前 N/类，测试只用 1test；所有组共用同一测试集（公平）。

红线：结果仅内部工程记录，MVP 阶段不得对外报告任何准确率；Kappa 是诚实口径。

运行（Windows PowerShell，m3 venv，仓库根）：
  $env:PYTHONPATH = "D:/校企合作项目/bci-decoder"
  .deepworks/venv_m3/Scripts/python.exe bci-decoder/scripts/m4_calibration.py --subjects 1 --pipeline csp
"""
from __future__ import annotations

import argparse
import csv
import os
import sys
import time
from pathlib import Path

import numpy as np

_DEFAULT_MNE_DATA = Path("D:/校企合作项目/.deepworks/mne_data")
DEFAULT_OUT = Path("D:/校企合作项目/docs/evidence/M4_calibration_20261117")
SFREQ = 250.0
WINDOW = 500
STEP = 125
CUE_IDX = 250
N_EPOCH = 1001
N_STEP = [10, 20, 30]  # 校准梯度（每类 trial 数）


def _sos_notch(sfreq=SFREQ):
    from scipy.signal import iirnotch, tf2sos

    b, a = iirnotch(50.0, 30.0, fs=sfreq)
    return tf2sos(b, a)


def _sos_band(sfreq=SFREQ):
    from scipy.signal import butter

    return butter(4, [8.0, 30.0], btype="bandpass", fs=sfreq, output="sos")


def _offline_epoch(x, sos_n, sos_b):
    """离线预处理（与 M3 一致）：notch50 + bp8-30(4) + 空间 CAR（减全通道均值）。"""
    from scipy.signal import sosfiltfilt

    y = sosfiltfilt(sos_n, x, axis=-1)
    y = sosfiltfilt(sos_b, y, axis=-1)
    return y - y.mean(axis=0, keepdims=True)  # CAR


def _windows(x, starts):
    return np.stack([x[:, s : s + WINDOW] for s in starts])


def _build_pipe(reg=None):
    from sklearn.discriminant_analysis import LinearDiscriminantAnalysis as LDA
    from sklearn.pipeline import make_pipeline

    from mne.decoding import CSP

    return make_pipeline(
        CSP(n_components=4, log=True, reg=reg), LDA(solver="lsqr", shrinkage="auto")
    )


def _starts(only_win_count=False):
    s = np.arange(CUE_IDX, N_EPOCH - WINDOW + 1, STEP, dtype=int)
    return s


def _trials_to_windows(X, sos_n, sos_b):
    """X: (n_ep, n_ch, n_t) -> (n_ep*n_wpt, n_ch, WINDOW) 并返回每窗原始 trial 索引计数。"""
    wins = np.concatenate(
        [_windows(_offline_epoch(x, sos_n, sos_b), _starts()) for x in X], axis=0
    )
    return wins


def load_data(subjects, mne_data):
    os.environ["MNE_DATA"] = str(mne_data)
    Path(mne_data).mkdir(parents=True, exist_ok=True)
    from moabb.datasets import BNCI2014_001
    from moabb.paradigms import MotorImagery

    ev = ["left_hand", "right_hand"]
    paradigm = MotorImagery(events=ev, n_classes=2)
    dataset = BNCI2014_001()
    out = {}
    t0 = time.time()
    for subj in subjects:
        epochs, y, meta = paradigm.get_data(
            dataset, subjects=[subj], return_epochs=True
        )
        y_int = np.asarray([0 if v == "left_hand" else 1 for v in y])
        out[subj] = (epochs.get_data(), y_int, np.asarray(meta["session"]))
        print(f"[M4] 加载 S{subj:02d} trials={len(y_int)} ({(time.time()-t0):.1f}s)")
    return out, ev


def _first_n_per_class(X, y, n):
    idxs = []
    for c in np.unique(y):
        c_idx = np.where(y == c)[0]
        idxs.append(c_idx[:n])
    idx = np.concatenate(idxs)
    return X[idx], y[idx]


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(description="M4 D1 个人校准 vs 免校准（BCI IV 2a）")
    parser.add_argument("--subjects", type=str, default="1,2,3,4,5,6,7,8,9")
    parser.add_argument("--pipeline", choices=["csp", "both"], default="csp")
    parser.add_argument("--csp-reg", type=str, default=None, help="CSP 正则化，默认与 M3 一致 reg=None")
    parser.add_argument("--p1-migrate", action="store_true",
                        help="P1 对照：迁移校准——CSP 空间在 8 人 0train 全局数据上 fit，"
                             "个人校准只 fit 线性 LDA（不改变主证据默认路径）")
    parser.add_argument("--mne-data", type=str, default=str(_DEFAULT_MNE_DATA))
    parser.add_argument("--out-dir", type=str, default=str(DEFAULT_OUT))
    parser.add_argument("--n-step", type=str, default=",".join(map(str, N_STEP)))
    args = parser.parse_args()

    subjects = [int(s) for s in args.subjects.split(",")]
    n_steps = [int(v) for v in args.n_step.split(",")]
    pipelines = ["csp"] if args.pipeline == "csp" else ["csp", "riemann"]
    out_dir = Path(args.out_dir)

    print(f"[M4] subjects={subjects} pipelines={pipelines} 梯度={n_steps}")
    data, _ = load_data(subjects, Path(args.mne_data))
    sos_n, sos_b = _sos_notch(), _sos_band()
    starts = _starts()
    n_wpt = len(starts)

    from sklearn.metrics import accuracy_score, cohen_kappa_score

    out_dir.mkdir(parents=True, exist_ok=True)
    summary = {}  # subj -> { 'nocal': kappa, 'cal': {N: kappa}, 'acc_nocal':.., 'acc_cal':{N:..} }

    for p in pipelines:
        print("=" * 74)
        print(f"[M4] pipeline = {p}")
        print("=" * 74)
        S = {}
        for te_subj in subjects:
            tr_subjs = [s for s in subjects if s != te_subj]
            if not tr_subjs:
                raise SystemExit('M4: no-calibration needs >=2 subjects (--subjects 1,2)')

            # —— 测试窗口（所有人共用同一个 1test，公平）——
            ep, y_te, sess = data[te_subj]
            idx_te = sess == "1test"
            Xte = ep[idx_te]
            y_te_int = y_te[idx_te]
            Xte_w = _trials_to_windows(Xte, sos_n, sos_b)
            y_te_win = np.repeat(y_te_int, n_wpt)

            row = {"subject": te_subj}

            # ① 免校准：8 人 0train 训练
            x_tr_all, y_tr_all = [], []
            for s in tr_subjs:
                ep_s, y_s, sess_s = data[s]
                idx = sess_s == "0train"
                X = ep_s[idx]
                wins = _trials_to_windows(X, sos_n, sos_b)
                x_tr_all.append(wins)
                y_tr_all.append(np.repeat(y_s[idx], n_wpt))
            Xtr = np.concatenate(x_tr_all, axis=0)
            Ytr = np.concatenate(y_tr_all)
            np.random.seed(0)
            pipe = _build_pipe(reg=args.csp_reg)
            pipe.fit(Xtr, Ytr)
            pred = pipe.predict(Xte_w)
            k = cohen_kappa_score(y_te_win, pred)
            a = accuracy_score(y_te_win, pred)
            row["nocal_kappa"], row["nocal_acc"] = k, a
            print(
                f"[M4] S{te_subj:02d} 免校准(8人LOO) win-acc={a:.3f} kappa={k:+.3f}"
            )

            # ② 个人校准：0train 前 N/类，逐档
            ep0, y0, sess0 = data[te_subj]
            idx0 = sess0 == "0train"
            X0 = ep0[idx0]
            y0_int = y0[idx0]
            row_cal_k, row_cal_a = {}, {}
            for N in n_steps:
                Xn, yn = _first_n_per_class(X0, y0_int, N)
                Xn_w = _trials_to_windows(Xn, sos_n, sos_b)
                yn_w = np.repeat(yn, n_wpt)
                np.random.seed(0)
                if args.p1_migrate:
                    # —— P1 对照：迁移校准（全局空间 + 个体线性判据）——
                    # 不改主证据路径；Xtr/Ytr = 8 人 0train 全局窗口（① 已算），
                    # CSP 只在该全局数据上 fit 一次做空间变换，个人校准仅拟合 LDA。
                    from sklearn.discriminant_analysis import (
                        LinearDiscriminantAnalysis as LDA,
                    )
                    from mne.decoding import CSP

                    _csp = CSP(n_components=4, log=True, reg=None)
                    _csp.fit(Xtr, Ytr)
                    Fn = _csp.transform(Xn_w)
                    Ft = _csp.transform(Xte_w)
                    _lda = LDA(solver="lsqr", shrinkage="auto")
                    _lda.fit(Fn, yn_w)
                    pc = _lda.predict(Ft)
                else:
                    pipe_c = _build_pipe(reg=args.csp_reg)
                    pipe_c.fit(Xn_w, yn_w)
                    pc = pipe_c.predict(Xte_w)
                kc = cohen_kappa_score(y_te_win, pc)
                ac = accuracy_score(y_te_win, pc)
                row_cal_k[N], row_cal_a[N] = kc, ac
                print(
                    f"[M4]   S{te_subj:02d} 校准N={N:2d}/类 训练trial={2*N} "
                    f"win-acc={ac:.3f} kappa={kc:+.3f}"
                )
            row["cal_kappa"] = row_cal_k
            row["cal_acc"] = row_cal_a
            S[te_subj] = row

        # —— 汇总 ——
        k_no = np.mean([S[s]["nocal_kappa"] for s in S])
        print("-" * 74)
        print(f"[M4] {p} 免校准均值 kappa={k_no:+.3f}")
        for N in n_steps:
            k_cal = np.mean([S[s]["cal_kappa"][N] for s in S])
            print(f"[M4] {p} 个人校准N={N:2d}/类 均值 kappa={k_cal:+.3f}  Δ={k_cal-k_no:+.3f}")
        print("-" * 74)

        # —— csv ——
        csv_path = out_dir / f"matrix_{p}.csv"
        with open(csv_path, "w", newline="", encoding="utf-8-sig") as f:
            w = csv.writer(f)
            head = ["subject", "nocal_kappa", "nocal_acc"]
            head += [f"cal{K}_kappa" for K in n_steps]
            head += [f"cal{K}_acc" for K in n_steps]
            w.writerow(head)
            for s in subjects:
                r = S[s]
                w.writerow(
                    [r["subject"], round(r["nocal_kappa"], 4), round(r["nocal_acc"], 4)]
                    + [round(r["cal_kappa"][K], 4) for K in n_steps]
                    + [round(r["cal_acc"][K], 4) for K in n_steps]
                )
        print(f"[M4] csv 写入 {csv_path}")

        # —— png 曲线 ——
        try:
            import matplotlib

            matplotlib.use("Agg")
            import matplotlib.pyplot as plt

            plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei"]
            plt.rcParams["axes.unicode_minus"] = False

            fig, ax = plt.subplots(figsize=(7.5, 5))
            for s in subjects:
                xs = n_steps
                ys = [S[s]["cal_kappa"][N] for N in n_steps]
                ax.plot(xs, ys, "-o", lw=1.3, ms=4, label=f"S{s:02d}")
            ax.axhline(k_no, ls="--", color="gray", lw=1.2)
            ax.text(
                n_steps[0],
                k_no - 0.02,
                f"免校准(8人LOO)均值 {k_no:+.2f}",
                color="gray",
                fontsize=9,
            )
            ax.set_xlabel("个人校准数据量（每类 trial 数；约2/4/6分钟）")
            ax.set_ylabel("Kappa (窗口级, session2 测试)")
            ax.set_title(
                f"M4 D1 个人校准梯度 ({p}) — BCI IV 2a {len(subjects)} 受试",
                fontsize=11,
            )
            ax.grid(alpha=0.3)
            ax.legend(fontsize=7, ncol=3, loc="lower right")
            png_path = out_dir / f"gradient_{p}.png"
            fig.tight_layout()
            fig.savefig(png_path, dpi=150)
            print(f"[M4] png 写入 {png_path}")
        except Exception as e:  # 画图失败不阻塞数字
            print(f"[M4] 绘图跳过: {type(e).__name__}: {e}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
