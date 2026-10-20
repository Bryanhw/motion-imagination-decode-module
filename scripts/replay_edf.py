"""Replay R12 in time order and write one prediction message per task cue."""
import argparse
import json
import time
from dataclasses import dataclass
from pathlib import Path

import joblib
import mne
import numpy as np
from scipy.signal import sosfilt

from eeg_events import imagery_events
from preprocess import ROOT, Config, make_filter

EDF = ROOT / "data" / "S001R12.edf"
ARTIFACTS = ROOT / "artifacts"
MODEL = ARTIFACTS / "s001_csp_lda.joblib"
METADATA = ARTIFACTS / "s001_csp_lda.json"
OFFLINE_PREDICTIONS = ARTIFACTS / "r12_predictions.npy"
MESSAGES = ARTIFACTS / "replay_messages.jsonl"
BLOCK_LOG = ARTIFACTS / "replay_blocks.jsonl"
TRIAL_LOG = ARTIFACTS / "replay_trials.jsonl"
INTENTS = {0: "LEFT_HAND", 1: "RIGHT_HAND"}


@dataclass(frozen=True)
class Block:
    start: int
    stop: int  # exclusive
    data: np.ndarray


def read_blocks(raw, picks, block_samples, real_time):
    """Yield only the current EDF block; the decoder never receives raw."""
    sfreq = raw.info["sfreq"]
    for start in range(0, raw.n_times, block_samples):
        stop = min(start + block_samples, raw.n_times)
        if real_time:
            time.sleep((stop - start) / sfreq)
        yield Block(start, stop, raw.get_data(picks=picks, start=start, stop=stop))


class StreamDecoder:
    def __init__(self, model, metadata, cue_samples):
        self.model = model
        self.sfreq = float(metadata["sfreq_hz"])
        self.channels = list(metadata["channel_names"])
        low, high = metadata["filter"]["low_high_hz"]
        config = Config(low_hz=low, high_hz=high, order=metadata["filter"]["order"])
        if metadata["filter"]["kind"] != "causal Butterworth SOS bandpass" or metadata["filter"]["initial_state"] != "zeros per recording":
            raise ValueError("模型要求的滤波规则与回放器不兼容")
        self.sos = make_filter(self.sfreq, config)
        self.state = np.zeros((self.sos.shape[0], len(self.channels), 2))
        self.history = []  # 仅含已经送达并完成滤波的块
        self.received = 0
        self.last_filter_ms = 0.0
        self.cues = list(cue_samples)  # 只有事件采样点；真实标签不送入解码器
        self.next_cue = 0
        start_s, end_s = metadata["epoch_seconds_after_cue"]
        self.start_offset = round(start_s * self.sfreq)
        self.stop_offset = round(end_s * self.sfreq)
        self.window_samples = int(metadata["epoch_samples"])
        if self.stop_offset - self.start_offset != self.window_samples:
            raise ValueError("模型窗口长度与时间参数不一致")

    def feed(self, block):
        """Accept one new block; emit at most one decision per now-complete cue."""
        if block.start != self.received:
            raise ValueError(f"数据块丢失、重复或乱序：期望起点 {self.received}，收到 {block.start}")
        if block.stop <= block.start or block.data.shape != (len(self.channels), block.stop - block.start):
            raise ValueError("数据块维度或采样范围不正确")
        if not np.isfinite(block.data).all():
            raise ValueError("数据块含 NaN/Inf，停止预测")
        filter_started = time.perf_counter()
        filtered, self.state = sosfilt(self.sos, block.data, axis=-1, zi=self.state)
        self.last_filter_ms = (time.perf_counter() - filter_started) * 1000
        self.history.append(filtered)
        self.received = block.stop
        emitted = []
        while self.next_cue < len(self.cues):
            cue = self.cues[self.next_cue]
            end = cue + self.stop_offset
            if end > self.received:
                break
            start = cue + self.start_offset
            if start < 0:
                raise ValueError("任务窗口超出记录起点")
            # History contains only samples delivered so far. Slicing cannot see future EEG.
            available = np.concatenate(self.history, axis=1)
            window = available[:, start:end]
            if window.shape != (len(self.channels), self.window_samples):
                raise ValueError("已到达数据不足以组成模型窗口")
            began = time.perf_counter()
            label = int(self.model.predict(window[np.newaxis, :, :])[0])
            compute_ms = (time.perf_counter() - began) * 1000
            if label not in INTENTS:
                raise ValueError(f"模型输出未知类别 {label}")
            sequence = self.next_cue  # per-source strictly increasing; also trial ID
            message = {"version": 1, "sequence": sequence,
                       "intent": INTENTS[label], "source": "replay",
                       "timestamp": round(block.stop / self.sfreq, 6)}
            detail = {"sequence": sequence, "cue_sample": cue,
                      "cue_s": cue / self.sfreq, "window_start_s": start / self.sfreq,
                      "window_end_s": end / self.sfreq, "output_data_s": block.stop / self.sfreq,
                      "signal_wait_s": (end - cue) / self.sfreq,
                      "output_wall_unix_s": time.time(),
                      "prediction_compute_ms": compute_ms, "prediction_label": label,
                      "message": message}
            emitted.append((message, detail))
            self.next_cue += 1
        return filtered, emitted


def run(real_time=False, block_seconds=0.25):
    for path in (EDF, MODEL, METADATA, OFFLINE_PREDICTIONS):
        if not path.is_file():
            raise FileNotFoundError(f"缺少 {path}；请先运行训练或下载步骤")
    metadata = json.loads(METADATA.read_text(encoding="utf-8"))
    if metadata["test_run"] != EDF.name:
        raise ValueError("模型元数据的测试记录不是 R12")
    # Only load a model created locally by this project or otherwise trusted.
    model = joblib.load(MODEL)
    raw = mne.io.read_raw_edf(EDF, preload=False, verbose="ERROR")
    sfreq = float(raw.info["sfreq"])
    picks = mne.pick_types(raw.info, eeg=True, exclude=[])
    names = [raw.ch_names[index] for index in picks]
    if sfreq != metadata["sfreq_hz"] or names != metadata["channel_names"]:
        raise ValueError("EDF 采样率或 EEG 通道名称/顺序与模型元数据不一致，停止预测")
    block_samples = round(block_seconds * sfreq)
    if block_seconds <= 0 or block_samples <= 0:
        raise ValueError("块时长必须大于零")
    events, event_id = imagery_events(raw)
    cues = [int(event[0]) for event in events]
    truth = [0 if event[2] == event_id["T1"] else 1 for event in events]
    if len(cues) != len(set(cues)):
        raise ValueError("出现重复的任务提示采样点")
    decoder = StreamDecoder(model, metadata, cues)
    ARTIFACTS.mkdir(exist_ok=True)
    messages, details, block_rows, filtered_parts = [], [], [], []
    started = time.perf_counter()
    for block in read_blocks(raw, picks, block_samples, real_time):
        filtered, emitted = decoder.feed(block)
        filtered_parts.append(filtered)
        block_rows.append({"start_sample": block.start, "stop_sample_exclusive": block.stop,
                           "start_s": block.start / sfreq, "stop_s": block.stop / sfreq,
                           "filter_compute_ms": decoder.last_filter_ms})
        for message, detail in emitted:
            # Labels are attached here, after predict has returned.
            detail["true_label"] = truth[detail["sequence"]]
            details.append(detail)
            messages.append(message)
            print(f"trial {message['sequence']:2d}: cue {detail['cue_s']:6.2f}s, "
                  f"signal [{detail['window_start_s']:.2f}, {detail['window_end_s']:.2f})s, "
                  f"output {message['timestamp']:.2f}s, {message['intent']}, "
                  f"truth {detail['true_label']}, compute {detail['prediction_compute_ms']:.2f} ms")
    wall_seconds = time.perf_counter() - started
    if decoder.received != raw.n_times or block_rows[-1]["stop_sample_exclusive"] != raw.n_times:
        raise RuntimeError("回放没有覆盖完整记录")
    if decoder.next_cue != len(cues) or len(messages) != len(cues):
        raise RuntimeError("有任务未输出，可能窗口超出记录边界")
    sequences = [message["sequence"] for message in messages]
    if sequences != list(range(len(cues))):
        raise RuntimeError("预测序号丢失、重复或乱序")
    # Verification only, after playback: compare the accumulated stream with one-shot filtering.
    whole = sosfilt(decoder.sos, raw.get_data(picks=picks), axis=-1)
    streamed = np.concatenate(filtered_parts, axis=1)
    difference = float(np.max(np.abs(whole - streamed)))
    if not np.allclose(whole, streamed, rtol=1e-10, atol=1e-12):
        raise RuntimeError(f"分块与一次性滤波不一致：最大差值 {difference:g} V")
    offline = np.load(OFFLINE_PREDICTIONS, allow_pickle=False)
    online = np.array([0 if message["intent"] == "LEFT_HAND" else 1 for message in messages])
    if not np.array_equal(offline, online):
        bad = np.flatnonzero(offline != online).tolist()
        raise RuntimeError(f"回放与离线预测不一致，任务序号：{bad}；请查滤波状态、窗口边界、通道顺序和采样点")
    for path, rows in ((MESSAGES, messages), (BLOCK_LOG, block_rows), (TRIAL_LOG, details)):
        path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")
    print(f"块数 {len(block_rows)}，覆盖 {raw.n_times} 点；任务 {len(cues)}，每次恰好一条预测")
    print(f"整段/分块滤波最大差值 {difference:.3e} V；与离线 R12 预测一致 {len(cues)}/{len(cues)}")
    print(f"信号等待：每次提示后至少 {decoder.stop_offset / sfreq:.2f} 秒数据；"
          f"本次回放墙钟时间 {wall_seconds:.2f} 秒（模式 {'真实速度' if real_time else '快速'}）")
    print(f"滤波累计计算 {sum(row['filter_compute_ms'] for row in block_rows):.2f} ms；"
          f"预测累计计算 {sum(row['prediction_compute_ms'] for row in details):.2f} ms")
    print(f"JSONL：{MESSAGES}；块记录：{BLOCK_LOG}；核对详情：{TRIAL_LOG}")
    raw.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="R12 EDF 按时间分块回放并预测")
    parser.add_argument("--real-time", action="store_true", help="每块按 EDF 时长等待")
    parser.add_argument("--block-seconds", type=float, default=0.25, help="块时长，默认 0.25 秒")
    args = parser.parse_args()
    try:
        run(real_time=args.real_time, block_seconds=args.block_seconds)
    except (OSError, ValueError, RuntimeError) as error:
        raise SystemExit(f"回放失败：{error}")
