"""LSL 实时数据源。

LSL（Lab Streaming Layer）是脑机接口领域事实标准的数据流协议，
绝大多数采集设备（Neuracle、OpenBCI、g.tec 等）都能通过 LSL 发布数据。
只要设备端起了 LSL 流，把本模块的 kind 改成 "lsl" 即可接入真实设备。
"""

from __future__ import annotations

from typing import Iterator, Sequence

import numpy as np

from ..types import EEGChunk
from .base import Source


class LSLSource(Source):
    def __init__(
        self,
        stream_name: str = "BCI-EEG",
        sfreq: float = 250.0,
        ch_names: Sequence[str] = (),
        chunk_samples: int = 25,
        resolve_timeout: float = 5.0,
    ):
        self.stream_name = stream_name
        self.sfreq = float(sfreq)
        self.ch_names = list(ch_names)
        self.chunk_samples = int(chunk_samples)
        self.resolve_timeout = float(resolve_timeout)
        self._inlet = None

    def start(self) -> None:
        try:
            from pylsl import StreamInlet, resolve_byprop
        except ImportError as e:  # pragma: no cover
            raise RuntimeError(
                "未安装 pylsl。请执行：pip install pylsl"
            ) from e

        streams = resolve_byprop("name", self.stream_name, timeout=self.resolve_timeout)
        if not streams:
            raise RuntimeError(
                f"在 {self.resolve_timeout}s 内未找到名为 {self.stream_name!r} 的 LSL 流。"
                "请确认采集软件已开始发布数据。"
            )
        self._inlet = StreamInlet(streams[0], max_buflen=360)
        # 用设备实际采样率覆盖配置，避免配置错误导致时间戳漂移
        try:
            info = self._inlet.info()
            self.sfreq = float(info.nominal_srate())
        except Exception:  # pragma: no cover
            pass

    def stream(self) -> Iterator[EEGChunk]:
        if self._inlet is None:
            self.start()
        while True:
            samples, ts = self._inlet.pull_chunk(
                timeout=1.0, max_samples=self.chunk_samples
            )
            if not samples:
                continue
            arr = np.asarray(samples, dtype=np.float64).T   # (n_ch, n_samples)
            yield EEGChunk(
                data=arr,
                sfreq=self.sfreq,
                t0=float(ts[0]),
                ch_names=self.ch_names,
            )

    def stop(self) -> None:
        self._inlet = None
