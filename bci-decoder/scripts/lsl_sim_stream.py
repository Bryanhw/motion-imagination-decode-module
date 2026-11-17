"""本地发布仿真 EEG 流（pylsl StreamOutlet），让 LSL 链路无设备自检。

背景：RA2（设备型号/通道顺序/流名书面确认）未到时，pylsl 的「发现流→抓取→判读」
代码路径从未被验证过。`lsl_selftest.py --from-npy` 只能验判读算法，不能验 pylsl 取流。
本脚本在本地推一条 8 通道 EEG 仿真流，让 `--list / --check` 无真机也能完整跑通。

能验什么 / 不能验什么：
  [能] pylsl 可用、流发现、抓取+判读、在线链路 LSL 接入代码路径
  [不能] 真实通道顺序——仿真数据是自造的，最终靠真机静息判读(--check 60) + RA2。
  判读结论不构成对仿真数据的任何性能陈述。

用法（两个终端，都在 bci-decoder/ 下）：
  终端 1：.venv/Scripts/python.exe scripts/lsl_sim_stream.py --seconds 30
  终端 2：.venv/Scripts/python.exe scripts/lsl_selftest.py --list
          .venv/Scripts/python.exe scripts/lsl_selftest.py --check 20
"""

from __future__ import annotations

import argparse
import sys
import time
from typing import Callable, List, Sequence

import numpy as np

# 演示通道顺序 = 项目固定 8 通道顺序（红线 4：顺序即语义，不得改动）
SIM_CH_NAMES: List[str] = ["C3", "Cz", "C4", "CP3", "CP4", "P3", "P4", "Oz"]

# 枕区 alpha：通道名 -> 10Hz 分量幅值（让 alpha 判读能找到枕区）
ALPHA_CHANNELS = {"P3": 0.35, "P4": 0.35, "Oz": 0.9}
BASE_AMP = 0.4     # 8-30Hz 基底正弦幅值（mu 一带）
NOISE_AMP = 0.25   # 白噪声幅值
LINE_AMP = 0.12    # 50Hz 工频干扰幅值（演示，不在判读用的 4-40Hz 内）

# 相邻共享慢波：提高相邻相关、压低对侧远距相关（演示几何一致性判读）
ADJACENT_SHARED = [
    ("C3", "CP3", 12.0, 0.5),
    ("C4", "CP4", 12.0, 0.5),
    ("P3", "Oz", 11.0, 0.4),
    ("P4", "Oz", 11.0, 0.4),
]


def simulate_block(
    n_ch: int = 8,
    sfreq: float = 250.0,
    duration_sec: float = 30.0,
    seed: int = 0,
    ch_names: Sequence[str] = SIM_CH_NAMES,
    alpha: bool = True,
) -> np.ndarray:
    """生成 (n_ch, n_t) 仿真 EEG（float32）。确定性命中 seed。"""
    n_t = int(round(duration_sec * sfreq))
    rng = np.random.default_rng(seed)
    t = np.arange(n_t) / sfreq
    data = np.zeros((n_ch, n_t))
    for i in range(n_ch):
        data[i] = (
            BASE_AMP * np.sin(2 * np.pi * 9.0 * t)
            + NOISE_AMP * rng.standard_normal(n_t)
            + LINE_AMP * np.sin(2 * np.pi * 50.0 * t)
        )
    names = list(ch_names)
    if alpha:
        for name, amp in ALPHA_CHANNELS.items():
            if name in names:
                data[names.index(name)] += amp * np.sin(2 * np.pi * 10.0 * t)
    for a, b, freq, amp in ADJACENT_SHARED:
        if a in names and b in names:
            shared = amp * np.sin(2 * np.pi * freq * t)
            data[names.index(a)] += shared
            data[names.index(b)] += shared
    return data.astype(np.float32)


def run(
    push: Callable[[Sequence[np.float32]], None],
    data: np.ndarray,
    sfreq: float = 250.0,
) -> int:
    """按真实节奏把仿真数据逐个样本推给 outlet。返回推送样本总数。"""
    step = max(1, int(round(sfreq / 20)))
    t0 = time.monotonic()
    per_sample = 1.0 / sfreq
    sent = 0
    start = 0
    while start < data.shape[1]:
        chunk = data[:, start:start + step].T  # (n_samples, n_ch)
        for row in chunk:
            push([np.float32(v) for v in row])
            sent += 1
        start += step
        # 按墙钟节奏推进，避免超发
        remain = t0 + sent * per_sample - time.monotonic()
        if remain > 0:
            time.sleep(remain)
    return sent


def build_outlet(
    stream_name: str, stream_type: str, sfreq: float,
    n_ch: int, ch_names: Sequence[str],
):
    """用 pylsl StreamOutlet 发布流，写入标准 XDF 通道名元数据。"""
    from pylsl import StreamInfo, StreamOutlet

    info = StreamInfo(stream_name, stream_type, n_ch, sfreq, "float32",
                      "sim_" + stream_name)
    ch = info.desc().append_child("channels")
    for name in list(ch_names)[:n_ch]:
        ch_node = ch.append_child("channel")
        ch_node.append_child_value("label", name)
        ch_node.append_child_value("unit", "microvolts")
        ch_node.append_child_value("type", "EEG")
    return StreamOutlet(info)


def main() -> int:
    ap = argparse.ArgumentParser(
        description="本地发布 8 通道仿真 EEG 流（pylsl），配合 lsl_selftest 无设备自检"
    )
    ap.add_argument("--stream-name", default="sim_mi_8ch", help="LSL 流名")
    ap.add_argument("--stream-type", default="EEG", help="LSL 流类型")
    ap.add_argument("--sfreq", type=float, default=250.0, help="采样率（默认 250）")
    ap.add_argument("--n-ch", type=int, default=len(SIM_CH_NAMES), help="通道数（默认 8）")
    ap.add_argument("--seconds", type=float, default=30.0, help="推流时长（秒）")
    ap.add_argument("--seed", type=int, default=0, help="随机种子（确定性复现）")
    ap.add_argument("--no-alpha", action="store_true", help="关闭枕区 alpha 仿真")
    args = ap.parse_args()

    if not (1 <= args.n_ch <= len(SIM_CH_NAMES)):
        raise SystemExit("--n-ch 应在 1..{} 之间".format(len(SIM_CH_NAMES)))

    try:
        outlet = build_outlet(args.stream_name, args.stream_type, args.sfreq,
                              args.n_ch, SIM_CH_NAMES)
    except ImportError:
        raise SystemExit("未安装 pylsl。请先执行：pip install pylsl") from None

    print("[sim] 已发布流：name={!r} type={!r} ch={} sfreq={:g}，将推 {:g}s...".format(
        args.stream_name, args.stream_type, args.n_ch, args.sfreq, args.seconds),
        file=sys.stderr)
    print("[sim] 在另一个终端运行 scripts/lsl_selftest.py --list 和 --check 抓取验证。",
          file=sys.stderr)

    data = simulate_block(args.n_ch, args.sfreq, args.seconds, args.seed,
                          alpha=not args.no_alpha)
    sent = run(outlet.push_sample, data, args.sfreq)
    print("[sim] 完成，共推 {} 个样本。".format(sent), file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
