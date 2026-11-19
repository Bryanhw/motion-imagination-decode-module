# -*- coding: utf-8 -*-
"""M4 E1: brainda 独立实现互证 D1 Kappa (BCI IV 2a, 9 subjects)."""
from __future__ import annotations

import argparse
import csv
import os
import sys
import time
from pathlib import Path

import numpy as np

os.environ["MNE_DATA"] = r"D:/校企合作项目/.deepworks/mne_data"
import mne.utils.check


def _auto_no(msg, *a, **k):
    return "n"


mne.utils.check._safe_input = _auto_no

import mne
from metabci.brainda.datasets.bnci import BNCI2014001
from metabci.brainda.algorithms.decomposition.csp import csp_kernel, csp_feature
from sklearn.discriminant_analysis import LinearDiscriminantAnalysis as LDA
from sklearn.metrics import accuracy_score, cohen_kappa_score

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))
from m4_calibration import (
    SFREQ, WINDOW, STEP, N_EPOCH, N_STEP,
    _sos_notch, _sos_band, _starts,
    _trials_to_windows, _first_n_per_class,
)

TMIN, TMAX = 2.0, 6.0
_EVENT_LEFT, _EVENT_RIGHT = 1, 2


def raw_to_epochs_22ch(raw, tmin=TMIN, tmax=TMAX):
    """picks=eeg -> 22ch, same as MOABB. Returns (X, y_int) or (None, None).

    MOABB MotorImagery applies raw.filter(8,32,method='iir',picks='data')
    BEFORE epoching; replicate that here (verified: first trial max|X-Xm|=0).
    """
    raw = raw.copy().filter(l_freq=8, h_freq=32, method="iir",
                            picks="data", verbose=False)
    events = mne.find_events(
        raw, stim_channel="STI 014", shortest_event=1,
        min_duration=0.001, consecutive=True, verbose=False,
    )
    if len(events) == 0:
        return None, None
    mask = np.isin(events[:, 2], [_EVENT_LEFT, _EVENT_RIGHT])
    events = events[mask]
    if len(events) == 0:
        return None, None
    ep = mne.Epochs(raw, events, event_id=None, picks="eeg",
                    tmin=tmin, tmax=tmax, baseline=None, preload=True,
                    reject=None, verbose=False)
    X = ep.get_data()
    y = events[:, 2] - 1
    return X, y


def load_subject(brainda, subject):
    """0train=session_1(T), 1test=session_0(E). X (n,22,1001)."""
    d = brainda.get_data([subject], verbose=False)[subject]
    out = {}
    for tag, sess_key in [("0train", "session_1"), ("1test", "session_0")]:
        Xs, ys = [], []
        for raw in d[sess_key].values():
            X, y = raw_to_epochs_22ch(raw)
            if X is not None:
                Xs.append(X)
                ys.append(y)
        if not Xs:
            raise RuntimeError(f"S{subject:02d} {tag}: no left/right trials")
        out[tag] = (np.concatenate(Xs, axis=0), np.concatenate(ys))
    return out


def csp_lda_fit(Xw, yw, n_components=4):
    W, D, A = csp_kernel(Xw, yw)
    F = csp_feature(W, Xw, n_components=n_components)
    lda = LDA(solver="lsqr", shrinkage="auto")
    lda.fit(F, yw)
    return lda, W


def csp_lda_predict(W, Xw, lda, n_components=4):
    F = csp_feature(W, Xw, n_components=n_components)
    return lda.predict(F)


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description="M4 E1 brainda crosscheck")
    parser.add_argument("--subjects", type=str, default="1,2,3,4,5,6,7,8,9")
    parser.add_argument("--out-dir", type=str,
                        default=r"D:/校企合作项目/.deepworks/tmp/M4_e1_brainda_20261119")
    parser.add_argument("--n-step", type=str, default=",".join(map(str, N_STEP)))
    parser.add_argument("--w-only", action="store_true", help="only no-calibration")
    args = parser.parse_args()
    n_steps = [int(v) for v in args.n_step.split(",")]
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    brainda = BNCI2014001()
    sos_n, sos_b = _sos_notch(), _sos_band()
    starts = _starts()
    n_wpt = len(starts)
    subjects = [int(s) for s in args.subjects.split(",")]

    data = {}
    t0 = time.time()
    for s in subjects:
        data[s] = load_subject(brainda, s)
        nt0 = len(data[s]["0train"][0])
        nt1 = len(data[s]["1test"][0])
        print(f"[E1] S{s:02d} 0train={nt0} 1test={nt1} ({time.time()-t0:.1f}s)")

    summary = {}
    ref = {10: 0.269, 20: 0.364, 30: 0.353}
    for te_subj in subjects:
        tr_subjs = [s for s in subjects if s != te_subj]
        Xte, y_te = data[te_subj]["1test"]
        Xte_w = _trials_to_windows(Xte, sos_n, sos_b)
        y_te_win = np.repeat(y_te, n_wpt)
        row = {"subject": te_subj}

        x_tr, y_tr = [], []
        for s in tr_subjs:
            X, y = data[s]["0train"]
            x_tr.append(_trials_to_windows(X, sos_n, sos_b))
            y_tr.append(np.repeat(y, n_wpt))
        Xtr = np.concatenate(x_tr, axis=0)
        Ytr = np.concatenate(y_tr)
        np.random.seed(0)
        lda, W = csp_lda_fit(Xtr, Ytr)
        pc = csp_lda_predict(W, Xte_w, lda)
        row["nocal_kappa"] = cohen_kappa_score(y_te_win, pc)
        row["nocal_acc"] = accuracy_score(y_te_win, pc)
        print(f"[E1] S{te_subj:02d} nocal kappa={row['nocal_kappa']:+.3f} acc={row['nocal_acc']:.3f}")

        row["cal_kappa"], row["cal_acc"] = {}, {}
        if not args.w_only:
            X0, y0 = data[te_subj]["0train"]
            for N in n_steps:
                Xn, yn = _first_n_per_class(X0, y0, N)
                Xn_w = _trials_to_windows(Xn, sos_n, sos_b)
                yn_w = np.repeat(yn, n_wpt)
                np.random.seed(0)
                lda_c, W_c = csp_lda_fit(Xn_w, yn_w)
                pc_c = csp_lda_predict(W_c, Xte_w, lda_c)
                kc = cohen_kappa_score(y_te_win, pc_c)
                ac = accuracy_score(y_te_win, pc_c)
                row["cal_kappa"][N], row["cal_acc"][N] = kc, ac
                print(f"[E1]   S{te_subj:02d} N={N:2d} kappa={kc:+.3f} acc={ac:.3f}")
        summary[te_subj] = row

    k_no = np.mean([summary[s]["nocal_kappa"] for s in subjects])
    print("-" * 70)
    print(f"[E1] nocal mean kappa={k_no:+.3f}  (D1 ref 0.191)")
    if not args.w_only:
        for N in n_steps:
            k_cal = np.mean([summary[s]["cal_kappa"][N] for s in subjects])
            print(f"[E1] cal N={N:2d} mean kappa={k_cal:+.3f} delta={k_cal-k_no:+.3f} (D1 ref {ref[N]})")
    print("-" * 70)

    csv_path = out_dir / "matrix_brainda_csp.csv"
    with open(csv_path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["subject", "nocal_kappa", "nocal_acc"]
                   + [f"cal{K}_kappa" for K in n_steps]
                   + [f"cal{K}_acc" for K in n_steps])
        for s in subjects:
            r = summary[s]
            w.writerow([r["subject"], round(r["nocal_kappa"], 4), round(r["nocal_acc"], 4)]
                       + [round(r["cal_kappa"][K], 4) for K in n_steps]
                       + [round(r["cal_acc"][K], 4) for K in n_steps])
    print(f"[E1] csv -> {csv_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
