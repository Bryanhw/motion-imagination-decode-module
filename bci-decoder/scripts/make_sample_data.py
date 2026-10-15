"""生成一段连续的模拟脑电数据 (.npy)，用于验证 replay（离线回放）通道。

用途：在没有真实采集数据时，把历史数据"当成实时流"重放，检验在线链路。
真实场景中，这个文件应该换成你们采集/下载的 (n_channels, n_samples) 数据。

用法：
    python scripts/make_sample_data.py --out data/sample_continuous.npy --seconds 60
"""

from __future__ import annotations

import argparse
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bci_decoder.config import DEFAULT_CH_NAMES  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description="生成连续模拟脑电数据")
    ap.add_argument("--out", default="data/sample_continuous.npy")
    ap.add_argument("--sfreq", type=float, default=250.0)
    ap.add_argument("--seconds", type=float, default=60.0)
    ap.add_argument("--channels", type=int, default=8)
    ap.add_argument("--label-period", type=float, default=4.0, help="每多少秒切换一次想象类别")
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args()

    n_ch = min(args.channels, len(DEFAULT_CH_NAMES))
    names = list(DEFAULT_CH_NAMES[:n_ch])
    n = int(args.sfreq * args.seconds)
    rng = np.random.default_rng(args.seed)

    t = np.arange(n) / args.sfreq
    label = ((t // args.label_period) % 2).astype(int)

    alpha = np.sin(2 * np.pi * 10.0 * t)
    gain = np.ones((n_ch, n))
    if "C3" in names:
        gain[names.index("C3")] = 1.0 + 0.8 * (1 - label)
    if "C4" in names:
        gain[names.index("C4")] = 1.0 + 0.8 * label

    data = 15.0 * alpha[None, :] * gain + 5.0 * rng.standard_normal((n_ch, n))

    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    np.save(args.out, data)
    print(f"已生成：{args.out}  形状={data.shape}  通道={names}  {args.seconds}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
