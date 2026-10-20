"""Prepare one subject: R04/R08 for training, R12 for testing.

No model is fitted here. All filter and window settings are fixed in Config.
"""
from dataclasses import dataclass
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import mne
import numpy as np
from scipy.signal import butter, sosfilt

from eeg_events import LABELS, imagery_events

ROOT = Path(__file__).resolve().parents[1]
TRAIN_RUNS = ("S001R04.edf", "S001R08.edf")
TEST_RUN = "S001R12.edf"
FIGURE = ROOT / "data" / "filter_comparison.png"


@dataclass(frozen=True)
class Config:
    low_hz: float = 8.0
    high_hz: float = 30.0
    order: int = 4
    start_s: float = 1.0
    end_s: float = 3.0
    extreme_uv: float = 500.0
    flat_std_uv: float = 0.1


def make_filter(sfreq, config):
    """One fixed causal filter, usable for a whole recording or live blocks."""
    if not 0 < config.low_hz < config.high_hz < sfreq / 2:
        raise ValueError("带通频率必须在 0 与奈奎斯特频率之间")
    return butter(config.order, [config.low_hz, config.high_hz],
                  btype="bandpass", fs=sfreq, output="sos")


def filter_blocks(signal, sos, block_size):
    """Carry zero-initialized filter state across consecutive time blocks."""
    state = np.zeros((sos.shape[0], signal.shape[0], 2))
    pieces = []
    for start in range(0, signal.shape[1], block_size):
        block, state = sosfilt(sos, signal[:, start:start + block_size],
                               axis=-1, zi=state)
        pieces.append(block)
    return np.concatenate(pieces, axis=-1)


def check_block_equivalence(signal, sos):
    """Compare whole and streamed filtering under the same zero initial state."""
    sample = signal[:, :min(signal.shape[1], 1600)]
    whole = sosfilt(sos, sample, axis=-1)
    streamed = filter_blocks(sample, sos, block_size=137)
    difference = float(np.max(np.abs(whole - streamed)))
    if not np.allclose(whole, streamed, rtol=1e-10, atol=1e-12):
        raise RuntimeError(f"分块滤波与一次性滤波不一致：最大差值 {difference:g} V")
    return difference


def read_run(filename, config, expected_names=None, expected_rate=None):
    path = ROOT / "data" / filename
    if not path.is_file():
        raise FileNotFoundError(f"缺少 {path}；请先运行 scripts/download_data.py")
    raw = mne.io.read_raw_edf(path, preload=True, verbose="ERROR")
    sfreq = float(raw.info["sfreq"])
    picks = mne.pick_types(raw.info, eeg=True, exclude=[])
    names = [raw.ch_names[index] for index in picks]
    if not names:
        raise ValueError(f"{filename} 没有 EEG 通道")
    if expected_names is not None and names != expected_names:
        raise ValueError(f"{filename} 的 EEG 通道名称或顺序与 R04 不一致")
    if expected_rate is not None and sfreq != expected_rate:
        raise ValueError(f"{filename} 的采样率 {sfreq:g} Hz 与 R04 的 {expected_rate:g} Hz 不一致")

    continuous = raw.get_data(picks=picks)
    if not np.isfinite(continuous).all():
        raise ValueError(f"{filename} 的连续信号含 NaN/Inf，停止处理")
    events, event_id = imagery_events(raw)
    sos = make_filter(sfreq, config)
    filtered = sosfilt(sos, continuous, axis=-1)  # zero state at each recording start

    start_offset = round(config.start_s * sfreq)
    stop_offset = round(config.end_s * sfreq)
    if start_offset < 0 or stop_offset <= start_offset:
        raise ValueError("片段时间范围无效")
    size = stop_offset - start_offset
    X, y = [], []
    excluded = {"超出记录边界": 0, "片段有缺失值": 0}
    warnings = {"极端幅度": 0, "平直通道": 0}
    for event in events:
        start, stop = int(event[0]) + start_offset, int(event[0]) + stop_offset
        if start < 0 or stop > filtered.shape[1]:
            excluded["超出记录边界"] += 1
            continue
        segment = filtered[:, start:stop]
        if not np.isfinite(segment).all():
            excluded["片段有缺失值"] += 1
            continue
        if np.max(np.abs(segment)) * 1e6 > config.extreme_uv:
            warnings["极端幅度"] += 1
        if np.any(np.std(segment, axis=1) * 1e6 < config.flat_std_uv):
            warnings["平直通道"] += 1
        X.append(segment)
        y.append(0 if event[2] == event_id["T1"] else 1)
    if not X:
        raise ValueError(f"{filename} 没有可用片段")
    result = (np.stack(X), np.asarray(y, dtype=np.int64))
    print(f"{filename}: 提示 {len(events)}，保留 {len(y)}，左 {y.count(0)}，右 {y.count(1)}；"
          f"排除 {excluded}；异常报告 {warnings}")
    raw.close()
    return result, names, sfreq, continuous, filtered, sos


def plot_comparison(before, after, names, sfreq):
    """Show the same C3 channel and time interval before and after filtering."""
    channel = "C3.." if "C3.." in names else names[0]
    index = names.index(channel)
    start, stop = int(3 * sfreq), int(8 * sfreq)
    times = np.arange(start, stop) / sfreq
    fig, axes = plt.subplots(2, 1, figsize=(9, 5), sharex=True)
    axes[0].plot(times, before[index, start:stop] * 1e6, lw=0.8)
    axes[1].plot(times, after[index, start:stop] * 1e6, lw=0.8)
    axes[0].set_title(f"{channel}: original")
    axes[1].set_title(f"{channel}: causal 8-30 Hz bandpass")
    for axis in axes:
        axis.set_ylabel("Voltage (uV)")
    axes[1].set_xlabel("Time in recording (s)")
    fig.tight_layout()
    fig.savefig(FIGURE, dpi=150)
    plt.close(fig)


def prepare_data(config=Config()):
    """Return X_train, y_train, X_test, y_test, and fixed metadata.

    Labels are 0=left (T1), 1=right (T2). Each EDF stays wholly in one split.
    """
    arrays = []
    names = rate = None
    max_difference = None
    for filename in (*TRAIN_RUNS, TEST_RUN):
        pair, run_names, run_rate, original, filtered, sos = read_run(
            filename, config, names, rate)
        if names is None:
            names, rate = run_names, run_rate
            max_difference = check_block_equivalence(original, sos)
            plot_comparison(original, filtered, names, rate)
        arrays.append(pair)
    X_train = np.concatenate([arrays[0][0], arrays[1][0]])
    y_train = np.concatenate([arrays[0][1], arrays[1][1]])
    X_test, y_test = arrays[2]
    metadata = {"channel_names": names, "sfreq": rate,
                "filter_hz": (config.low_hz, config.high_hz),
                "filter_order": config.order,
                "epoch_seconds": (config.start_s, config.end_s),
                "train_runs": TRAIN_RUNS, "test_run": TEST_RUN,
                "block_max_difference_volts": max_difference}
    print(f"通道顺序完全一致：是（{len(names)} 个 EEG 通道）；采样率：{rate:g} Hz")
    print("EEG 通道顺序：" + ", ".join(names))
    print(f"起步参数：Butterworth {config.order} 阶因果带通 {config.low_hz:g}-{config.high_hz:g} Hz；"
          f"提示后 [{config.start_s:g}, {config.end_s:g}) 秒")
    print(f"X_train {X_train.shape}, y_train {y_train.shape}；左 {(y_train == 0).sum()}，右 {(y_train == 1).sum()}")
    print(f"X_test  {X_test.shape}, y_test  {y_test.shape}；左 {(y_test == 0).sum()}，右 {(y_test == 1).sum()}")
    print(f"每段 {X_train.shape[-1]} 点 = {X_train.shape[-1] / rate:.3f} 秒")
    print(f"同初始状态下整段/分块滤波最大差值：{max_difference:.3e} V（一致）")
    print(f"对比图：{FIGURE}")
    return X_train, y_train, X_test, y_test, metadata


if __name__ == "__main__":
    try:
        prepare_data()
    except (OSError, ValueError, RuntimeError) as error:
        raise SystemExit(f"预处理失败：{error}")
