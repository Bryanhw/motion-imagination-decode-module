"""数据源抽象接口。

只要实现 stream()，就能接入解码引擎——这是模块可替换性的关键。
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Iterator

from ..types import EEGChunk


class Source(ABC):
    """脑电数据源。"""

    @abstractmethod
    def stream(self) -> Iterator[EEGChunk]:
        """产生 EEGChunk 的生成器（可无限循环）。"""

    def start(self) -> None:
        """建立连接、准备资源。"""

    def stop(self) -> None:
        """释放资源。"""

    def __enter__(self) -> "Source":
        self.start()
        return self

    def __exit__(self, *exc) -> None:
        self.stop()
