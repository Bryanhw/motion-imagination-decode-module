"""用真实墙钟时长压测 mock 解码链路，记录当前进程 RSS 与耗时变化。

在 bci-decoder/ 执行；默认连续运行 3600 秒，不限数据块数。
仅验证工程稳定性，不评估真实脑电准确率，不代替游戏联调。
"""

from __future__ import annotations

import argparse
import csv
import ctypes
from ctypes import wintypes
from datetime import datetime
import json
import math
import os
from pathlib import Path
import sys
import time
import traceback

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np

from bci_decoder.config import Config
from bci_decoder.core import DecoderEngine
from bci_decoder.sources import build_source
from bci_decoder.sources.base import Source


def current_rss_bytes() -> int:
    """读取当前 RSS/WorkingSet，而非内存峰值；不需要安装 psutil。"""
    if sys.platform != "win32":
        raise RuntimeError("本脚本的 RSS 采样目前支持 Windows 演示机")

    class MemoryCounters(ctypes.Structure):
        _fields_ = [
            ("cb", wintypes.DWORD),
            ("PageFaultCount", wintypes.DWORD),
            *[(name, ctypes.c_size_t) for name in (
                "PeakWorkingSetSize", "WorkingSetSize", "QuotaPeakPagedPoolUsage",
                "QuotaPagedPoolUsage", "QuotaPeakNonPagedPoolUsage",
                "QuotaNonPagedPoolUsage", "PagefileUsage", "PeakPagefileUsage",
            )],
        ]

    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.GetCurrentProcess.argtypes = []
    kernel.GetCurrentProcess.restype = wintypes.HANDLE
    kernel.K32GetProcessMemoryInfo.argtypes = [
        wintypes.HANDLE, ctypes.POINTER(MemoryCounters), wintypes.DWORD,
    ]
    kernel.K32GetProcessMemoryInfo.restype = wintypes.BOOL
    counters = MemoryCounters()
    counters.cb = ctypes.sizeof(counters)
    if not kernel.K32GetProcessMemoryInfo(
        kernel.GetCurrentProcess(), ctypes.byref(counters), counters.cb,
    ):
        raise ctypes.WinError(ctypes.get_last_error())
    return int(counters.WorkingSetSize)


class TimedSource(Source):
    """保留引擎原有 run/push 路径，只增加墙钟停止与进度采样。"""

    def __init__(self, inner, seconds, started, on_progress):
        self.inner = inner
        self.seconds = seconds
        self.started = started
        self.on_progress = on_progress
        self.chunks = 0

    def start(self):
        self.inner.start()

    def stop(self):
        self.inner.stop()

    def stream(self):
        for chunk in self.inner.stream():
            if time.perf_counter() - self.started >= self.seconds:
                break
            self.chunks += 1
            yield chunk
            self.on_progress(self.chunks)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Windows mock 解码链路长跑与 RSS 记录")
    parser.add_argument("--config", default="configs/demo_online.yaml")
    parser.add_argument("--seconds", type=float, default=3600.0)
    parser.add_argument("--report-every", type=float, default=30.0)
    parser.add_argument("--out-dir", default="")
    args = parser.parse_args(argv)
    if any(not math.isfinite(v) or v <= 0 for v in (args.seconds, args.report_every)):
        parser.error("--seconds 和 --report-every 必须是有限正数")

    cfg = Config.load(args.config)
    if cfg.source.kind != "mock":
        parser.error("当前长跑脚本使用 mock 源；请提供 mock 配置")
    cfg.source.realtime = False
    engine = DecoderEngine(cfg)
    inner = build_source(cfg.source)
    # 在创建产物前验证当前平台能够采样当前 RSS。
    current_rss_bytes()

    out_dir = Path(args.out_dir or (
        "artifacts/soak_" + datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    ))
    if out_dir.exists() and any(out_dir.iterdir()):
        parser.error("输出目录已有文件，请换一个 --out-dir，避免覆盖历史记录")
    out_dir.mkdir(parents=True, exist_ok=True)
    cfg.save(str(out_dir / "effective_config.yaml"))
    metadata = {
        "pid": os.getpid(), "python": sys.version, "executable": sys.executable,
        "started_at": datetime.now().astimezone().isoformat(),
        "requested_seconds": args.seconds, "report_every_seconds": args.report_every,
        "source": cfg.source.kind, "realtime": cfg.source.realtime,
        "mode": "decoder core only; no console/jsonl/websocket output sinks",
        "rss_method": "Windows K32GetProcessMemoryInfo.WorkingSetSize",
        "timing_history": "bounded engine history; per-report statistics use available recent new samples",
        "timing_history_limit": engine.compute_times_ms.maxlen,
    }
    (out_dir / "metadata.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8",
    )

    fields = [
        "timestamp", "elapsed_seconds", "chunks", "outputs", "rss_bytes",
        "rss_mib", "latest_compute_ms", "interval_outputs", "interval_p50_ms",
        "interval_p95_ms", "latency_history_count", "interval_sample_count",
    ]
    samples = []  # 每个进度间隔保留一行，不收集每个数据块的监测记录。
    started = time.perf_counter()
    last_report = started
    previous_output_count = 0
    status, error, exit_code = "incomplete", None, 2

    with (out_dir / "progress.csv").open("w", encoding="utf-8-sig", newline="") as csv_file, (
        out_dir / "run.log"
    ).open("w", encoding="utf-8") as log:
        writer = csv.DictWriter(csv_file, fieldnames=fields)
        writer.writeheader()

        def record(chunks, force=False):
            nonlocal last_report, previous_output_count
            now = time.perf_counter()
            if not force and now - last_report < args.report_every:
                return
            history = list(engine.compute_times_ms)
            new_outputs = engine.n_outputs - previous_output_count
            sample_count = min(new_outputs, len(history))
            interval = np.asarray(history[-sample_count:] if sample_count else [], dtype=float)
            rss = current_rss_bytes()
            row = {
                "timestamp": datetime.now().astimezone().isoformat(),
                "elapsed_seconds": round(now - started, 6),
                "chunks": chunks, "outputs": engine.n_outputs,
                "rss_bytes": rss, "rss_mib": rss / 1024**2,
                "latest_compute_ms": history[-1] if history else None,
                "interval_outputs": new_outputs,
                "interval_sample_count": int(interval.size),
                "interval_p50_ms": float(np.percentile(interval, 50)) if interval.size else None,
                "interval_p95_ms": float(np.percentile(interval, 95)) if interval.size else None,
                "latency_history_count": len(history),
            }
            samples.append(row)
            writer.writerow(row)
            csv_file.flush()
            message = (
                f"[{row['elapsed_seconds']:.1f}s] chunks={chunks} "
                f"outputs={engine.n_outputs} RSS={row['rss_mib']:.2f}MiB "
                f"latest_ms={row['latest_compute_ms']} p95_ms={row['interval_p95_ms']}"
            )
            print(message, flush=True)
            log.write(message + "\n")
            log.flush()
            last_report, previous_output_count = now, engine.n_outputs

        source = TimedSource(inner, args.seconds, started, record)
        print(f"长跑开始：PID={os.getpid()}，目标 {args.seconds:g} 秒，产物 {out_dir.resolve()}", flush=True)
        record(0, force=True)
        try:
            engine.run(source=source, sinks=[])
            elapsed = time.perf_counter() - started
            if elapsed >= args.seconds and engine.n_outputs > 0:
                status, exit_code = "completed", 0
        except KeyboardInterrupt:
            status, error, exit_code = "interrupted", "KeyboardInterrupt", 130
        except Exception:
            status, error, exit_code = "error", traceback.format_exc(), 1
            log.write(error)
            print(error, file=sys.stderr, flush=True)
        finally:
            record(source.chunks, force=True)
            actual_seconds = time.perf_counter() - started
            summary = {
                "status": status, "error": error,
                "requested_seconds": args.seconds, "actual_seconds": actual_seconds,
                "chunks": source.chunks, "outputs": engine.n_outputs,
                "rss_first_bytes": samples[0]["rss_bytes"],
                "rss_last_bytes": samples[-1]["rss_bytes"],
                "rss_delta_mib": (samples[-1]["rss_bytes"] - samples[0]["rss_bytes"]) / 1024**2,
                "progress_samples": len(samples),
                "full_hour_elapsed": status == "completed" and actual_seconds >= 3600,
                "memory_acceptance": "pending review of trend after warm-up; not auto-passed",
            }
            (out_dir / "summary.json").write_text(
                json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8",
            )
            print(
                f"长跑结束：status={status}，实际 {actual_seconds:.2f}s；"
                "运行结束不代表内存稳定性已验收，请检查 progress.csv。",
                flush=True,
            )
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
