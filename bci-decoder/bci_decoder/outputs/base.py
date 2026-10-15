"""输出通道抽象接口。"""

from __future__ import annotations

from abc import ABC, abstractmethod

from ..types import DecoderOutput


class Sink(ABC):
    """解码结果的消费者。"""

    @abstractmethod
    def emit(self, out: DecoderOutput) -> None:
        ...

    def close(self) -> None:
        """释放资源。"""
