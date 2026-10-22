"""Convert a PhysioNet EEGMMIDB EDF run to the decoder's 8-channel replay format.

Requires optional dependency MNE: ``python -m pip install mne``.
The source EDF is left untouched. The converted file is a local test artifact.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np


CHANNELS = ["C3..", "Cz..", "C4..", "Cp3.", "Cp4.", "P3..", "P4..", "Oz.."]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=Path("data/eegmmidb_s001/S001R04.edf"))
    parser.add_argument("--output", type=Path, default=Path("artifacts/eegmmidb_s001r04_8ch_250hz.npy"))
    args = parser.parse_args(argv)
    if not args.input.is_file():
        parser.error(f"找不到 EDF 文件：{args.input}")

    try:
        import mne
    except ImportError as exc:
        parser.error("需要可选依赖 MNE；先运行 python -m pip install mne")

    raw = mne.io.read_raw_edf(args.input, preload=True, verbose="ERROR")
    missing = [name for name in CHANNELS if name not in raw.ch_names]
    if missing:
        parser.error(f"EDF 缺少所需通道：{missing}")
    raw.pick(CHANNELS)
    raw.resample(250.0, verbose="ERROR")
    # MNE returns SI volts; the decoder replay source expects microvolts.
    data_uv = raw.get_data() * 1e6
    if data_uv.ndim != 2 or not np.isfinite(data_uv).all():
        parser.error("EDF 转换后数据形状或数值异常")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    np.save(args.output, data_uv.astype(np.float32))
    print(f"已生成本地回放文件：{args.output} shape={data_uv.shape}, 250 Hz, microvolts")
    print("通道顺序：C3, Cz, C4, CP3, CP4, P3, P4, Oz；源 EDF 与标注未修改。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
