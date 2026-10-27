"""LSL 接入现场自检：列流、抓样本、验证通道顺序、生成配置片段。

背景：设备型号 / 通道顺序 / LSL 流名 三项本来需要企业书面确认，但迟迟拿不到。
本脚本用**数据本身**替代书面确认，把风险从"等人回复"变成"现场 3 分钟可判定"。

用法（在 bci-decoder/ 下）：

    python scripts/lsl_selftest.py --list
    python scripts/lsl_selftest.py --check 60                 # 抓 60 s 静息数据做判读
    python scripts/lsl_selftest.py --check 60 --emit-config   # 顺带打印配置片段
    python scripts/lsl_selftest.py --from-npy data/x.npy --ch-names C3,Cz,...   # 无设备时自验

判读标准（只依赖静息态，不需要受试者做任务）：
  1. **枕区 alpha**：8–13 Hz 相对功率最强的通道应落在 {Oz, P3, P4} 里（闭眼更明显）。
  2. **几何一致性**：相邻电极相关（C3-CP3、C4-CP4、P3-Oz、P4-Oz）应高于其对侧远距电极
     （C3-P4、C4-P3），否则说明空间布局与标签不符。
  3. **左右对称**：C3 与 C4 的 mu 相对功率差距不应超过 3 倍（静息态），
     超出提示电极位置或接触异常。

结论分三级：PASS（顺序可信）/ WARN（可疑，建议人工核）/ FAIL（明显错位）。
"""

from __future__ import annotations

import argparse
import sys
from typing import Dict, List, Sequence

import numpy as np

TARGETS = ["C3", "Cz", "C4", "CP3", "CP4", "P3", "P4", "Oz"]
OCCIPITAL = {"Oz", "P3", "P4"}
ADJACENT = [("C3", "CP3"), ("C4", "CP4"), ("P3", "Oz"), ("P4", "Oz")]
CROSS = [("C3", "P4"), ("C4", "P3")]


# ---------------- 信号指标 ----------------
def _psd(sig: np.ndarray, sfreq: float) -> tuple[np.ndarray, np.ndarray]:
    from scipy.signal import welch

    nper = int(min(len(sig), max(64, 2 * sfreq)))
    f, p = welch(sig, fs=sfreq, nperseg=nper)
    return f, p


def rel_band_power(data: np.ndarray, sfreq: float, lo: float, hi: float,
                   total_lo: float = 4.0, total_hi: float = 40.0) -> np.ndarray:
    """每个通道在 [lo, hi] 的相对功率（占 4–40 Hz 的比例）。data: (n_ch, n_t)。"""
    out = []
    for ch in data:
        f, p = _psd(ch - ch.mean(), sfreq)
        band = (f >= lo) & (f <= hi)
        total = (f >= total_lo) & (f <= total_hi)
        denom = p[total].sum()
        out.append(p[band].sum() / denom if denom > 0 else 0.0)
    return np.asarray(out)


def corr_matrix(data: np.ndarray) -> np.ndarray:
    """通道间零延迟相关系数矩阵（先去掉直流）。"""
    x = data - data.mean(axis=1, keepdims=True)
    std = x.std(axis=1, keepdims=True)
    std[std == 0] = 1.0
    z = x / std
    return (z @ z.T) / z.shape[1]


# ---------------- 判读 ----------------
def evaluate(data: np.ndarray, ch_names: Sequence[str], sfreq: float) -> Dict:
    names = [n.strip() for n in ch_names]
    alpha = rel_band_power(data, sfreq, 8.0, 13.0)
    mu = rel_band_power(data, sfreq, 8.0, 12.0)
    corr = corr_matrix(data)
    pos = {n: i for i, n in enumerate(names)}

    order = np.argsort(alpha)[::-1]
    ranked = [(names[i], float(alpha[i])) for i in order]

    findings: List[str] = []
    verdict = "PASS"

    # 0) 数据健康检查：合成/近纯节律数据没有真实空间结构，判读不可靠
    if float(np.min(alpha)) > 0.75:
        verdict = "WARN"
        findings.append(
            "所有通道 alpha 占比 >75%，疑似合成或近纯节律数据，"
            "本判读不可靠 [WARN]（请用真实设备的静息数据）"
        )

    # 1) 枕区 alpha
    present_occ = [n for n in names if n in OCCIPITAL]
    if present_occ:
        top3 = [n for n, _ in ranked[:3]]
        if any(n in OCCIPITAL for n in top3):
            findings.append(f"枕区 alpha：前 3 名 {top3} 中含枕区通道 [OK]")
        else:
            verdict = "WARN"
            findings.append(f"枕区 alpha：前 3 名 {top3} 中**没有**枕区通道 [WARN]（顺序可疑）")

    # 2) 几何一致性
    adj_vals, cross_vals = [], []
    for a, b in ADJACENT:
        if a in pos and b in pos:
            adj_vals.append(float(corr[pos[a], pos[b]]))
    for a, b in CROSS:
        if a in pos and b in pos:
            cross_vals.append(float(corr[pos[a], pos[b]]))
    if adj_vals and cross_vals:
        adj_m, cross_m = float(np.mean(adj_vals)), float(np.mean(cross_vals))
        if adj_m > cross_m:
            findings.append(f"几何一致性：相邻均值 {adj_m:.2f} > 对侧远距均值 {cross_m:.2f} [OK]")
        else:
            verdict = "FAIL" if adj_m < cross_m - 0.05 else "WARN"
            findings.append(f"几何一致性：相邻 {adj_m:.2f} ≤ 远距 {cross_m:.2f} [FAIL]（布局与标签不符）")

    # 3) 左右对称（静息）
    if "C3" in pos and "C4" in pos:
        a, b = max(mu[pos["C3"]], 1e-9), max(mu[pos["C4"]], 1e-9)
        ratio = max(a, b) / min(a, b)
        if ratio <= 3.0:
            findings.append(f"C3/C4 mu 功率比 {ratio:.2f} [OK]")
        else:
            verdict = "WARN" if verdict == "PASS" else verdict
            findings.append(f"C3/C4 mu 功率比 {ratio:.2f} [WARN]（疑似接触不良或位置异常）")

    return {
        "verdict": verdict,
        "alpha_ranked": ranked,
        "findings": findings,
        "corr": corr,
        "names": names,
    }


def render(result: Dict, sfreq: float, duration: float) -> str:
    lines = []
    lines.append(f"LSL 通道顺序自检  采样率 {sfreq:g} Hz  时长 {duration:.1f} s")
    lines.append("=" * 64)
    lines.append("8–13 Hz 相对功率排名：")
    for i, (n, v) in enumerate(result["alpha_ranked"], 1):
        lines.append(f"  {i}. {n:<4s} {v*100:5.1f}%")
    lines.append("")
    lines.append("判读：")
    for f in result["findings"]:
        lines.append(f"  - {f}")
    lines.append("")
    lines.append(f"结论：{result['verdict']}")
    if result["verdict"] != "PASS":
        lines.append("处置：用 channel_index / channel_map 修正映射后重跑；"
                     "仍不明时用「睁眼/闭眼」复测（闭眼 alpha 应显著升高）再判定。")
    return "\n".join(lines)


# ---------------- 数据来源 ----------------
def from_lsl(seconds: float, stream_name: str, stream_type: str,
             timeout: float) -> tuple[np.ndarray, List[str], float]:
    try:
        from pylsl import StreamInlet, resolve_byprop
    except ImportError as e:
        raise SystemExit("未安装 pylsl（pip install pylsl）。无设备时可用 --from-npy。") from e

    streams = []
    if stream_name:
        streams = resolve_byprop("name", stream_name, timeout=timeout)
    if not streams:
        streams = resolve_byprop("type", stream_type, timeout=timeout)
    if not streams:
        raise SystemExit(f"{timeout}s 内未发现 LSL 流（name={stream_name!r} type={stream_type!r}）")

    st = streams[0]
    info = st
    print(f"[selftest] 使用流：name={info.name()!r} type={info.type()!r} "
          f"ch={info.channel_count()} sfreq={info.nominal_srate()}", file=sys.stderr)

    # 通道名
    labels: List[str] = []
    try:
        from bci_decoder.sources.lsl import channel_labels_of

        labels = channel_labels_of(info)
    except Exception:
        labels = []

    inlet = StreamInlet(st, max_buflen=360)
    sfreq = float(info.nominal_srate() or 250.0)
    need = int(seconds * sfreq)
    chunks, got = [], 0
    inlet.open_stream()
    while got < need:
        samples, _ = inlet.pull_chunk(timeout=2.0, max_samples=min(256, need - got))
        if not samples:
            break
        arr = np.asarray(samples, dtype=np.float64)
        chunks.append(arr)
        got += arr.shape[0]
    if not chunks:
        raise SystemExit("没有收到数据，检查设备是否在推流。")
    data = np.vstack(chunks).T  # (n_ch, n_t)

    if not labels or len(labels) != data.shape[0]:
        labels = [f"CH{i+1}" for i in range(data.shape[0])]
        print("[selftest][WARN] 设备未发布通道名，按 CH1..CHn 处理；"
              "判读只能验证数量与几何，无法验证命名。", file=sys.stderr)
    return data, labels, sfreq


def from_npy(path: str, ch_names: str, sfreq: float) -> tuple[np.ndarray, List[str], float]:
    data = np.load(path)
    if data.ndim != 2:
        raise SystemExit(f"数据形状应为 (n_ch, n_t)，实际 {data.shape}")
    names = [x.strip() for x in ch_names.split(",") if x.strip()]
    if len(names) != data.shape[0]:
        raise SystemExit(f"--ch-names 给了 {len(names)} 个，数据有 {data.shape[0]} 通道")
    return data, names, sfreq


def list_streams(timeout: float) -> None:
    try:
        from pylsl import resolve_stream
    except ImportError:
        raise SystemExit("未安装 pylsl（pip install pylsl）。")
    streams = resolve_stream("", timeout)
    if not streams:
        print(f"{timeout}s 内没有发现任何 LSL 流。")
        return
    print(f"发现 {len(streams)} 个流：")
    for i, s in enumerate(streams, 1):
        print(f"  [{i}] name={s.name()!r} type={s.type()!r} "
              f"ch={s.channel_count()} sfreq={s.nominal_srate()} "
              f"host={s.hostname()}")
    print("\n把对应 name 填到配置 source.stream_name；或留空用 source.stream_type 自动发现。")


def emit_config(idx: List[int], labels: Sequence[str], stream_name: str) -> str:
    lines = ["source:", "  kind: lsl", f"  stream_name: {stream_name}"]
    if labels and not all(l.startswith("CH") for l in labels):
        lines.append("  channel_map:")
        for k, i in enumerate(idx):
            lines.append(f"    {labels[i]}: {TARGETS[k]}")
    else:
        lines.append(f"  channel_index: {idx}")
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser(description="LSL 接入现场自检")
    ap.add_argument("--list", action="store_true", help="只列出可发现的 LSL 流")
    ap.add_argument("--check", type=float, default=0.0, metavar="SECONDS",
                    help="抓取指定秒数的数据并判读通道顺序（建议 60）")
    ap.add_argument("--stream-name", default="", help="流名（留空=按类型发现）")
    ap.add_argument("--stream-type", default="EEG", help="流类型（默认 EEG）")
    ap.add_argument("--timeout", type=float, default=10.0, help="发现流超时秒数")
    ap.add_argument("--from-npy", default="", help="离线自验：读 (n_ch,n_t) 的 .npy")
    ap.add_argument("--ch-names", default=",".join(TARGETS), help="--from-npy 时的通道名")
    ap.add_argument("--sfreq", type=float, default=250.0, help="--from-npy 时的采样率")
    ap.add_argument("--emit-config", action="store_true", help="打印可粘贴的配置片段")
    ap.add_argument("--out", default="", help="把报告写入文件")
    args = ap.parse_args()

    if args.list:
        list_streams(args.timeout)
        return 0

    if args.from_npy:
        data, names, sfreq = from_npy(args.from_npy, args.ch_names, args.sfreq)
    elif args.check > 0:
        data, names, sfreq = from_lsl(args.check, args.stream_name, args.stream_type, args.timeout)
    else:
        ap.print_help()
        return 2

    # 若设备通道数 > 目标 8，取前 8 做判读（完整映射由配置决定）
    if data.shape[0] > len(TARGETS):
        print(f"[selftest] 设备通道 {data.shape[0]} > 目标 {len(TARGETS)}，"
              f"仅用前 {len(TARGETS)} 通道演示判读。", file=sys.stderr)
        data = data[: len(TARGETS)]
        names = list(names[: len(TARGETS)])

    result = evaluate(data, names, sfreq)
    report = render(result, sfreq, data.shape[1] / sfreq)
    print(report)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(report + "\n")
        print(f"\n报告已写入 {args.out}")

    if args.emit_config:
        idx = list(range(len(names)))
        print("\n# ---- 可粘贴到配置 ----")
        print(emit_config(idx, names, args.stream_name))
        print("# ----------------------")

    return 0 if result["verdict"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
