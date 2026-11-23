# -*- coding: utf-8 -*-
"""M4 D1 -> D2: 把 BCI Competition IV 2a 指定受试/场次导出为解码器回放/校准输入格式。

背景（2026-11-17 阎浩文，D1 交接 D2 王释贤）：
  D1 证据链用 BNCI2014-001（BCI IV 2a）22 通道分析（见 m4_calibration.py 与
  docs/evidence/M4_calibration_20261117/）。D2 replay 链路输入 .npy (n_ch, n_t)、µV、
  250Hz（bci_decoder.sources.replay 契约），calibrate.py 的真实采集输入同为
  raw.npy + labels.npy（docs/calibration_flow.md §7）。

  关键通道事实：BCI IV 2a 22 通道为
    Fz FC3 FC1 FCz FC2 FC4 C5 C3 C1 Cz C2 C4 C6 CP3 CP1 CPz CP2 CP4 P1 Pz P2 POz
  其中【不含 P3、P4、Oz】（冻结 8 通道契约 C3,Cz,C4,CP3,CP4,P3,P4,Oz 有 3 个通道缺失）。
  因此 D2 回放若需这些通道，只能用 BCI IV 2a 外的数据（如 EEGMMIDB），或改用
  BCI IV 2a 的 22 通道全集 / 可用子集（ReplaySource 支持任意通道数）。本脚本默认导出
  22 通道全集（与 D1 模型口径一致），供 calibrate.py / replay 直接使用。

用法（Windows PowerShell，m3 venv，仓库根）：
  $env:PYTHONPATH = "D:/校企合作项目/bci-decoder"
  # S05 受试 session2(1test) 全部 trial 拼成连续流 + 标签
  .deepworks/venv_m3/Scripts/python.exe bci-decoder/scripts/m4_prepare_replay.py \
      --subject 5 --session 1test --out-dir artifacts/m4_replay

产出：
  artifacts/m4_replay/S05_1test_22ch_250hz.npy   # (22, n_t)，µV，float32（回放/校准原始段）
  artifacts/m4_replay/S05_1test_labels.npy       # 每 trial 标签（0=left_hand, 1=right_hand）
  artifacts/m4_replay/S05_1test_trials.csv       # trial 起点样本索引（拼接顺序），便于对齐

红线：本产物仅供公开数据回放联调（画面须标注“公开数据集回放”），不得作为真人性能证据；
  mock/公开数据不得用于对外报告准确率（红线 5/6）。
"""
from __future__ import annotations

import argparse
import csv
import os
from pathlib import Path

import numpy as np

_DEFAULT_MNE_DATA = Path("D:/校企合作项目/.deepworks/mne_data")
EVENTS = ["left_hand", "right_hand"]


def load_subject_epochs(subject: int, mne_data: Path):
    os.environ["MNE_DATA"] = str(mne_data)
    Path(mne_data).mkdir(parents=True, exist_ok=True)
    from moabb.datasets import BNCI2014_001
    from moabb.paradigms import MotorImagery

    paradigm = MotorImagery(events=EVENTS, n_classes=2)
    dataset = BNCI2014_001()
    epochs, y, meta = paradigm.get_data(dataset, subjects=[subject], return_epochs=True)
    y_int = np.asarray([0 if v == "left_hand" else 1 for v in y])
    sess = np.asarray(meta["session"])
    return epochs, y_int, sess


def main(argv: list[str] | None = None) -> int:
    if hasattr(__import__("sys").stdout, "reconfigure"):
        import sys
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--subject", type=int, required=True, help="BCI IV 2a 受试编号 1..9")
    ap.add_argument("--session", type=str, default="1test",
                    help="场次：1test(session2) / 0train(session1)")
    ap.add_argument("--mne-data", type=str, default=str(_DEFAULT_MNE_DATA))
    ap.add_argument("--out-dir", type=str, default="artifacts/m4_replay")
    args = ap.parse_args(argv)

    epochs, y_int, sess = load_subject_epochs(args.subject, Path(args.mne_data))
    ch_names = list(epochs.ch_names)
    sfreq = epochs.info.get("sfreq")
    mask = sess == args.session
    n = int(mask.sum())
    if n == 0:
        ap.error(f"受试 S{args.subject:02d} 无 session={args.session!r} 的 trial（可选：0train/1test）")

    X = epochs.get_data()[mask]  # (n_trials, n_ch, n_samples)
    Y = y_int[mask]
    # 按 trial 顺序拼成连续流（演示/回放用途；跨 trial 边缘为固定时长，与 D1 滑窗一致）
    # ⚠️ 单位：mne/moabb 的 get_data() 返回 SI 伏特，而 ReplaySource/calibrate 契约要求 µV，
    #    必须 ×1e6（与 prepare_eegmmidb_replay.py 相同；此前版本漏乘导致单位差 1e6，已修，2026-11-19）。
    data_uv = (X.transpose(1, 0, 2).reshape(X.shape[1], -1) * 1e6).astype(np.float32)  # (n_ch, n_trials*n_samples) 单位 µV
    if not np.isfinite(data_uv).all():
        ap.error("导出数据含非有限值")

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    tag = f"S{args.subject:02d}_{args.session}"
    np.save(out_dir / f"{tag}_22ch_{int(sfreq):.0f}hz.npy", data_uv)
    np.save(out_dir / f"{tag}_labels.npy", Y)

    with open(out_dir / f"{tag}_trials.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["trial_idx", "start_sample", "label", "class_1test"])
        for i in range(n):
            w.writerow([i, i * X.shape[2], int(Y[i]), EVENTS[Y[i]]])

    print(f"[m4-prepare] S{args.subject:02d} 通道({len(ch_names)}): {ch_names}")
    print(f"[m4-prepare] sfreq={sfreq:.0f}Hz  trial={n}  trial_len={X.shape[2]} 源采样"
          f"-> 连续流 shape={data_uv.shape} = {data_uv.shape[1]/sfreq:.1f}s")
    print(f"[m4-prepare] 写出: {out_dir / (tag + '_22ch_' + str(int(sfreq)) + 'hz.npy')}")
    print(f"[m4-prepare] 写出: {out_dir / (tag + '_labels.npy')}  分布 0/1 = "
          f"{int((Y==0).sum())}/{int((Y==1).sum())}")
    print("[m4-prepare] 注意：BCI IV 2a 不含 P3/P4/Oz；若要冻结 8 通道契约请改用"
          "替代数据（见文档头部说明）。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
