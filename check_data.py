"""Read one EDF recording and print a few beginner-friendly facts."""
from pathlib import Path
import sys

try:
    import mne
except ImportError:
    print("错误：当前 Python 环境没有安装 MNE。请先运行：python -m pip install -r requirements.txt")
    raise SystemExit(2)

# 这个脚本在项目根目录，因此 data/ 就在脚本旁边。
data_dir = Path(__file__).resolve().parent / "data"
edf_path = data_dir / "S001R04.edf"

if not edf_path.is_file():
    print(f"错误：找不到脑电文件：{edf_path}")
    print("请把 S001R04.edf 放进项目的 data 文件夹，再重新运行。")
    raise SystemExit(1)

print(f"文件路径：{edf_path}")
print(f"文件大小：{edf_path.stat().st_size:,} 字节")

try:
    raw = mne.io.read_raw_edf(edf_path, preload=False, verbose="ERROR")
except Exception as error:
    print(f"错误：MNE 无法读取这个 EDF 文件：{type(error).__name__}: {error}")
    print("文件可能下载不完整。请从 PhysioNet 重新下载 S001R04.edf。")
    raise SystemExit(1)

# raw 是 MNE 读取后的整段记录对象；info 保存采样率等测量信息。
info = raw.info
ch_names = raw.ch_names
sampling_rate = info["sfreq"]
duration_seconds = raw.n_times / sampling_rate

print(f"采样率：{sampling_rate:g} Hz")
print(f"EEG 通道数量：{len(ch_names)}")
print(f"前 8 个通道名称：{', '.join(ch_names[:8])}")
print(f"记录时长：{duration_seconds:.2f} 秒（{duration_seconds / 60:.2f} 分钟）")

# EDF+ 的事件文字由 MNE 放在 annotations 中；统计三种官方事件代码。
event_counts = {"T0": 0, "T1": 0, "T2": 0}
for description in raw.annotations.description:
    code = str(description).strip().upper().split()[-1]
    if code in event_counts:
        event_counts[code] += 1
print("事件数量：" + ", ".join(f"{code}={count}" for code, count in event_counts.items()))

raw.close()
