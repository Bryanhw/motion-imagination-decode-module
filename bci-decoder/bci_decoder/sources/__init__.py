"""数据源：同一接口下支持 mock（合成）/ replay（离线回放）/ lsl（实时设备）。"""

from __future__ import annotations

from ..config import SourceConfig
from .base import Source


def build_source(cfg: SourceConfig) -> Source:
    if cfg.kind == "mock":
        from .mock import MockSource

        return MockSource(
            sfreq=cfg.sfreq,
            ch_names=list(cfg.ch_names),
            chunk_samples=cfg.chunk_samples,
            realtime=cfg.realtime,
            seed=cfg.seed,
        )
    if cfg.kind == "replay":
        from .replay import ReplaySource

        return ReplaySource(
            path=cfg.path,
            sfreq=cfg.sfreq,
            ch_names=list(cfg.ch_names),
            chunk_samples=cfg.chunk_samples,
            speed=cfg.speed,
            loop=cfg.loop,
            realtime=cfg.realtime,
        )
    if cfg.kind == "lsl":
        from .lsl import LSLSource

        return LSLSource(
            stream_name=cfg.stream_name,
            sfreq=cfg.sfreq,
            ch_names=list(cfg.ch_names),
            chunk_samples=cfg.chunk_samples,
            resolve_timeout=cfg.resolve_timeout,
            stream_type=cfg.stream_type,
            channel_map=dict(cfg.channel_map or {}),
            channel_index=list(cfg.channel_index or []),
        )
    raise ValueError(f"未知的数据源类型: {cfg.kind}")


__all__ = ["Source", "build_source"]
