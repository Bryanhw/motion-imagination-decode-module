"""Check the three selected PhysioNet EEG Motor Movement/Imagery EDF files."""
from pathlib import Path
import sys

try:
    import mne
except ImportError:
    print("错误：没有安装 MNE。请先在项目虚拟环境中运行：python -m pip install -r requirements.txt")
    raise SystemExit(2)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data"
EXPECTED_FILES = ("S001R04.edf", "S001R08.edf", "S001R12.edf")


def main() -> int:
    """Read every expected recording and compare its basic properties."""
    missing = [name for name in EXPECTED_FILES if not (DATA_DIR / name).is_file()]
    if missing:
        print("错误：以下 EDF 文件缺失或不是普通文件：")
        for name in missing:
            print(f"  - data/{name}")
        print("请按 README.md 的下载步骤获取这三份文件后重试。")
        return 1

    summaries = []
    has_error = False
    for filename in EXPECTED_FILES:
        path = DATA_DIR / filename
        print(f"\n正在检查：{path.relative_to(PROJECT_ROOT)}")
        try:
            raw = mne.io.read_raw_edf(path, preload=False, verbose="ERROR")
            annotations = raw.annotations
            event_counts = {code: 0 for code in ("T0", "T1", "T2")}
            for description in annotations.description:
                normalized = str(description).strip().upper()
                # EDF+ files may prefix event labels with an annotation channel name.
                code = normalized.split()[-1] if normalized else ""
                if code in event_counts:
                    event_counts[code] += 1

            sfreq = float(raw.info["sfreq"])
            channel_names = list(raw.ch_names)
            duration = float(raw.n_times / sfreq)
            print(f"  读取成功；采样率：{sfreq:g} Hz")
            print(f"  通道数：{len(channel_names)}")
            print(f"  通道名称/顺序：{', '.join(channel_names)}")
            print(f"  时长：{duration:.2f} 秒（{duration / 60:.2f} 分钟）")
            print("  注释数量：" + ", ".join(f"{code}={event_counts[code]}" for code in event_counts))

            if event_counts["T1"] == 0 or event_counts["T2"] == 0:
                print("  错误：没有同时找到 T1 和 T2。请确认文件完整且为目标 EDF。")
                has_error = True
            if event_counts["T0"] == 0:
                print("  提示：没有找到 T0（休息）标记。")

            summaries.append((filename, sfreq, channel_names))
            raw.close()
        except Exception as exc:  # Show file-specific context instead of silently skipping a bad EDF.
            print(f"  错误：MNE 无法读取该文件：{type(exc).__name__}: {exc}")
            has_error = True

    if len(summaries) == len(EXPECTED_FILES):
        rates = [item[1] for item in summaries]
        channels = [item[2] for item in summaries]
        same_rate = all(rate == rates[0] for rate in rates[1:])
        same_order = all(names == channels[0] for names in channels[1:])
        print("\n三份文件一致性：")
        print(f"  采样率一致：{'是' if same_rate else '否'}")
        print(f"  通道顺序一致：{'是' if same_order else '否'}")
        if not same_rate:
            print("  错误：三份记录的采样率不一致。")
            has_error = True
        if not same_order:
            print("  错误：三份记录的通道数量或顺序不一致。")
            has_error = True

    if has_error:
        print("\n核验未通过。请根据上方提示检查文件，然后重新运行。")
        return 1
    print("\n核验通过：三份文件均可读取，左右手任务标记及一致性检查正常。")
    print("注意：本脚本只做数据核验，不训练模型。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
