"""Locate left/right imagery events and extract simple EEG segments."""
from pathlib import Path
import sys
from eeg_events import LABELS, imagery_events

try:
    import mne
    import matplotlib.pyplot as plt
except ImportError as error:
    print(f"错误：缺少依赖 {error.name}。请在项目虚拟环境中运行：python -m pip install -r requirements.txt")
    raise SystemExit(2)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
EDF_PATH = PROJECT_ROOT / "data" / "S001R04.edf"
FIGURE_PATH = PROJECT_ROOT / "data" / "continuous_vs_epochs.png"

# 起步参数：先观察提示后第 1 到第 3 秒，共 2 秒；这不是最佳设置结论。
EPOCH_START = 1.0
EPOCH_END = 3.0


def main() -> int:
    if not EDF_PATH.is_file():
        print(f"错误：找不到 EDF 文件：{EDF_PATH}")
        print("请先把 S001R04.edf 放到项目的 data 文件夹。")
        return 1

    print(f"读取文件：{EDF_PATH}")
    try:
        raw = mne.io.read_raw_edf(EDF_PATH, preload=True, verbose="ERROR")
    except Exception as error:
        print(f"错误：MNE 读取 EDF 失败：{type(error).__name__}: {error}")
        return 1

    # annotations 是 EDF 内的文字标记；events_from_annotations 把它们变成采样点事件表。
    events, event_id = mne.events_from_annotations(raw, verbose="ERROR")
    inverse_event_id = {number: description for description, number in event_id.items()}
    print("事件代码映射：" + ", ".join(f"{name}={number}" for name, number in event_id.items()))

    # 只保留左右手想象提示。事件第一列是样本序号，除以采样率得到秒数。
    try:
        selected_events, wanted = imagery_events(raw)
    except ValueError:
        print("错误：没有同时找到 T1 和 T2。请检查 EDF 文件和事件注释。")
        raw.close()
        return 1

    sfreq = raw.info["sfreq"]
    print("\n左右手任务提示：")
    for index, event in enumerate(selected_events[:8], start=1):
        code = inverse_event_id[event[2]]
        print(f"  {index:2d}. {event[0] / sfreq:7.3f} 秒  {code}  {LABELS[code]}")
    counts = {name: sum(event[2] == number for event in selected_events) for name, number in wanted.items()}
    print(f"\nT1 左手想象：{counts['T1']} 次")
    print(f"T2 右手想象：{counts['T2']} 次")

    # Epochs 的 tmin/tmax 相对于提示事件；这里取提示后 1 到 3 秒。
    epochs = mne.Epochs(
        raw,
        events,
        event_id=wanted,
        tmin=EPOCH_START,
        tmax=EPOCH_END,
        baseline=None,
        preload=True,
        reject_by_annotation=False,
        verbose="ERROR",
    )
    X = epochs.get_data()[:, :, :-1]
    y = epochs.events[:, 2]
    y_names = [inverse_event_id[int(code)] for code in y]
    left_count = y_names.count("T1")
    right_count = y_names.count("T2")
    dropped = len(selected_events) - len(epochs)
    actual_duration = X.shape[2] / sfreq if X.shape[2] else 0.0

    print("\n切片结果（X 的维度是：片段 × EEG 通道 × 每段时间点）：")
    print(f"  X.shape = {X.shape}")
    print(f"  y.shape = {y.shape}")
    print(f"  y 标签数量：左手想象={left_count}，右手想象={right_count}")
    print(f"  每段实际时长：{actual_duration:.3f} 秒")
    print(f"  因超出记录边界而丢弃的任务事件：{dropped} 次")
    print(f"  标签一一对应：X 有 {len(X)} 段，y 有 {len(y)} 个标签；相等={len(X) == len(y)}")

    # 画同一通道的一段连续原始波形，并用竖线标出一个提示时刻。
    channel_name = "C3.." if "C3.." in raw.ch_names else raw.ch_names[0]
    channel_index = raw.ch_names.index(channel_name)
    first_event = selected_events[0]
    event_sample = int(first_event[0])
    left_sample = max(0, event_sample - int(2 * sfreq))
    right_sample = min(raw.n_times, event_sample + int(5 * sfreq))
    signal = raw.get_data(picks=[channel_index], start=left_sample, stop=right_sample)[0] * 1e6
    time_axis = (range(left_sample, right_sample))
    time_seconds = [sample / sfreq for sample in time_axis]

    FIGURE_PATH.parent.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(10, 4))
    ax.plot(time_seconds, signal, linewidth=0.8)
    code = inverse_event_id[first_event[2]]
    event_time = first_event[0] / sfreq
    ax.axvline(event_time, color="red", linestyle="--", label=f"task cue {code}")
    ax.set_xlabel("Time (s)")
    ax.set_ylabel(f"{channel_name} voltage (uV)")
    ax.set_title("Continuous EEG and task cue")
    ax.legend()
    fig.tight_layout()
    fig.savefig(FIGURE_PATH, dpi=150)
    plt.close(fig)
    print(f"\n示意图已保存：{FIGURE_PATH}")

    raw.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
