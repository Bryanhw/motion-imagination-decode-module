# -*- coding: utf-8 -*-
"""M3: ITR（信息传输率，Wolpaw）逐受试/汇总计算（BCI IV 2a，内部工程记录）。
协议与伪在线/LOO 一致: 0train 训练 / 1test 测试; notch50+bp8-30(4)+CAR; csp/riemann+LDA; 窗2.0s/0.5s, trial 级 3 窗投票。
红线: 结果不对外。
"""
from __future__ import annotations

import argparse
import math
import os
import sys
import time
from pathlib import Path

import numpy as np

_DEFAULT_MNE_DATA = Path(r"D:\校企合作项目\.deepworks\mne_data")
SFREQ = 250.0
WINDOW = 500
STEP = 125
CUE_IDX = 250
N_EPOCH = 1001
TS_LIST = [2.0, 3.0, 4.0]


def _sos_notch(sfreq=SFREQ):
    from scipy.signal import iirnotch, tf2sos

    b, a = iirnotch(50.0, 30.0, fs=sfreq)
    return tf2sos(b, a)


def _sos_band(sfreq=SFREQ):
    from scipy.signal import butter

    return butter(4, [8.0, 30.0], btype="bandpass", fs=sfreq, output="sos")


def _offline_epoch(x, sos_n, sos_b):
    from scipy.signal import sosfiltfilt

    y = sosfiltfilt(sos_n, x, axis=-1)
    y = sosfiltfilt(sos_b, y, axis=-1)
    return y - y.mean(axis=0, keepdims=True)


def _windows(x, starts):
    return np.stack([x[:, s : s + WINDOW] for s in starts])


def _build_pipe(name):
    from sklearn.discriminant_analysis import LinearDiscriminantAnalysis as LDA
    from sklearn.pipeline import make_pipeline

    if name == "csp":
        from mne.decoding import CSP

        return make_pipeline(
            CSP(n_components=4, log=True, reg=None), LDA(solver="lsqr", shrinkage="auto")
        )
    if name == "riemann":
        from pyriemann.estimation import Covariances
        from pyriemann.tangentspace import TangentSpace

        return make_pipeline(
            Covariances(estimator="lwf"),
            TangentSpace(),
            LDA(solver="lsqr", shrinkage="auto"),
        )
    raise ValueError(name)


def itr_bits(p, n_classes):
    if p <= 1e-9:
        return 0.0
    p = min(max(p, 1e-9), 1.0 - 1e-9)
    if p < 1.0 / n_classes:
        return 0.0
    return math.log2(n_classes) + p * math.log2(p) + (1 - p) * math.log2((1 - p) / (n_classes - 1))


def itr_rate(acc, n_classes, t_s):
    return itr_bits(acc, n_classes) * 60.0 / t_s


def run(subjects, pipelines, mne_data):
    os.environ["MNE_DATA"] = mne_data
    Path(mne_data).mkdir(parents=True, exist_ok=True)

    from moabb.datasets import BNCI2014_001
    from moabb.paradigms import MotorImagery

    paradigm = MotorImagery(events=["left_hand", "right_hand"], n_classes=2)
    dataset = BNCI2014_001()
    epochs_all = {}
    t0 = time.time()
    for subj in subjects:
        epochs, y, meta = paradigm.get_data(dataset, subjects=[subj], return_epochs=True)
        epochs_all[subj] = (epochs, np.asarray(y), np.asarray(meta["session"]))
    print(f"[m3][itr] 加载 {len(subjects)} 受试用时 {time.time()-t0:.1f}s; 管线={pipelines}")

    sos_n, sos_b = _sos_notch(), _sos_band()
    starts = np.arange(CUE_IDX, N_EPOCH - WINDOW + 1, STEP, dtype=int)
    n_wpt = len(starts)

    from scipy.stats import mode
    from sklearn.metrics import accuracy_score, cohen_kappa_score

    for p in pipelines:
        print("=" * 78)
        print(f"[m3][itr] pipeline = {p}  (C=2, trial 级 3 窗多数投票)")
        print("=" * 78)
        pooled = {"hit_t": 0, "n_t": 0}
        sub_rates = {t: [] for t in TS_LIST}
        for te_subj in subjects:
            ep, y_te, sess = epochs_all[te_subj]
            idx = sess == "0train"
            Xtr = ep.get_data()[idx]
            ytr = np.asarray(y_te)[idx]
            idx_te = sess == "1test"
            Xte = ep.get_data()[idx_te]
            yte = np.asarray(y_te)[idx_te]
            tr_wins = np.concatenate([_windows(_offline_epoch(x, sos_n, sos_b), starts) for x in Xtr], axis=0)
            te_wins = np.concatenate([_windows(_offline_epoch(x, sos_n, sos_b), starts) for x in Xte], axis=0)
            np.random.seed(0)
            pipe = _build_pipe(p)
            pipe.fit(tr_wins, np.repeat(ytr, n_wpt))
            pred = pipe.predict(te_wins)

            uniq = np.unique(np.concatenate([yte, pred]))
            lab2int = {l: i for i, l in enumerate(uniq)}
            y_win = np.repeat(np.array([lab2int[v] for v in yte]), n_wpt)
            pred_i = np.array([lab2int[v] for v in pred])
            pred_t = mode(pred_i.reshape(-1, n_wpt), axis=1).mode.astype(int).ravel()
            y_t = np.array([lab2int[v] for v in yte])
            acc_t = accuracy_score(y_t, pred_t)
            k_t = cohen_kappa_score(y_t, pred_t)
            pooled["hit_t"] += int(np.sum(y_t == pred_t))
            pooled["n_t"] += int(y_t.size)
            itrs = [itr_rate(acc_t, 2, t) for t in TS_LIST]
            for i, t in enumerate(TS_LIST):
                sub_rates[t].append(itrs[i])
            print(
                f"[m3][itr] S{te_subj:02d} | trial-acc={acc_t:.3f} kappa={k_t:+.3f} | "
                f"ITR@{''.join([f'{t:.1f}s={itrs[i]:.2f}' + (', ' if i < len(TS_LIST)-1 else '') for i, t in enumerate(TS_LIST)])} bits/min"
            )
        print("-" * 78)
        for t in TS_LIST:
            mean_it = float(np.mean(sub_rates[t]))
            pooled_acc = pooled["hit_t"] / pooled["n_t"]
            pooled_it = itr_rate(pooled_acc, 2, t)
            print(
                f"[m3][itr] {p:8s} T={t:.1f}s: 逐受试平均 bits/min={mean_it:.2f} | "
                f"pooled acc={pooled_acc:.3f} pooled bits/min={pooled_it:.2f}"
            )
    return 0


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description="M3 ITR 计算")
    parser.add_argument("--subjects", type=str, default="1,2,3,4,5,6,7,8,9")
    parser.add_argument("--pipeline", choices=["csp", "riemann", "both"], default="both")
    parser.add_argument("--mne-data", type=str, default=str(_DEFAULT_MNE_DATA))
    args = parser.parse_args()
    subjects = [int(s) for s in args.subjects.split(",")]
    pipelines = ["csp", "riemann"] if args.pipeline == "both" else [args.pipeline]
    return run(subjects, pipelines, args.mne_data)


if __name__ == "__main__":
    sys.exit(main())
