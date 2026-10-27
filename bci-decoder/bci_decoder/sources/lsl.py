"""LSL 实时数据源（设备无关）。

设计目标：**在不确定设备型号/通道顺序/流名的情况下也能安全接入**。

三层防线：
1. **发现**：`stream_name` 留空时按 `stream_type`（默认 EEG）自动发现候选流，
   并打印候选清单，避免"流名猜错 → 连不上"。
2. **映射**：把设备实际通道重排到项目固定的 8 通道语义顺序
   （C3, Cz, C4, CP3, CP4, P3, P4, Oz）。支持三种方式，优先级从高到低：
   - `channel_index`：直接给设备索引（设备不发布通道名时用）；
   - `channel_map`：设备通道名 → 目标通道名（设备名不规范时用）；
   - 通道名同名直接匹配（设备名就是标准 10-20 名称时，不需要任何配置）。
3. **显式失败**：缺通道、数量不符、流不存在 —— 一律抛 `RuntimeError` 并打印
   设备实际通道清单与可用修法，**绝不静默补零 / 静默错位**
   （通道顺序错会让左右输出稳定相反，是本项目红线）。

未安装 pylsl 时给出明确安装提示；单元测试通过注入假模块验证映射逻辑。
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from typing import Dict, Iterator, List, Sequence

import numpy as np

from ..types import EEGChunk
from .base import Source


def _labels_from_desc(desc) -> List[str]:
    """从 LSL StreamInfo.desc() 里取通道名（标准 XDF `<channels><channel><label>`）。

    拿不到就返回空列表——调用方据此退化为索引映射。
    """
    labels: List[str] = []
    try:
        channels = desc.child("channels")
        if channels is not None:
            for ch in channels.children():
                label = ch.child_value("label")
                if label:
                    labels.append(str(label).strip())
            if labels:
                return labels
    except Exception:
        pass
    # 兜底：有些设备只给 XML 字符串
    try:
        xml = desc.to_xml() if hasattr(desc, "to_xml") else str(desc)
        root = ET.fromstring(xml)
        for node in root.iter("channel"):
            label = node.find("label")
            if label is not None and (label.text or "").strip():
                labels.append(label.text.strip())
    except Exception:
        return []
    return labels


def channel_labels_of(info) -> List[str]:
    """尽力获取设备通道名；失败返回空列表。"""
    try:
        desc = info.desc()
    except Exception:
        return []
    if desc is None:
        return []
    return _labels_from_desc(desc)


def resolve_index_map(
    targets: Sequence[str],
    device_labels: Sequence[str],
    channel_map: Dict[str, str] | None = None,
    channel_index: Sequence[int] | None = None,
    device_count: int | None = None,
) -> List[int]:
    """把目标通道顺序解析为设备索引列表（纯函数，便于测试）。

    Args:
        targets: 目标通道名，顺序即语义（必须是 8 通道固定顺序）。
        device_labels: 设备通道名（可能为空）。
        channel_map: 设备名 → 目标名 的别名表。
        channel_index: 直接指定的设备索引（按 targets 顺序）。
        device_count: 设备通道总数（device_labels 为空时用于同序退化判断）。

    Raises:
        RuntimeError: 缺通道 / 数量不符 / 无法确定顺序。
    """
    targets = [t.strip() for t in targets]
    if channel_index:
        idx = [int(i) for i in channel_index]
        if len(idx) != len(targets):
            raise RuntimeError(
                f"channel_index 长度 {len(idx)} 与目标通道数 {len(targets)} 不一致：{targets}"
            )
        n = device_count if device_count is not None else (max(idx) + 1 if idx else 0)
        bad = [i for i in idx if i < 0 or (n and i >= n)]
        if bad:
            raise RuntimeError(f"channel_index 越界：{bad}（设备通道数 {n}）")
        if len(set(idx)) != len(idx):
            raise RuntimeError(f"channel_index 有重复索引：{idx}")
        return idx

    if device_labels:
        # channel_map 是 设备名 -> 目标名，这里反查成 目标名 -> 设备名
        alias: Dict[str, str] = {}
        for dev_name, target_name in (channel_map or {}).items():
            alias[str(target_name).strip().lower()] = str(dev_name).strip().lower()
        lookup = {lab.strip().lower(): i for i, lab in enumerate(device_labels)}
        idx, missing = [], []
        used = set()
        for t in targets:
            want = alias.get(t.lower(), t.lower())
            i = lookup.get(want)
            if i is None or i in used:
                missing.append(t)
            else:
                idx.append(i)
                used.add(i)
        if missing:
            raise RuntimeError(
                "设备通道中找不到目标通道 "
                f"{missing}。\n设备实际通道（{len(device_labels)} 个）：{list(device_labels)}\n"
                "修法：在配置 source.channel_map 里写「设备通道名: 目标通道名」，"
                "或改用 source.channel_index 直接给索引（顺序同 "
                f"{targets}）。"
            )
        return idx

    # 设备不发布通道名
    n = device_count if device_count is not None else 0
    if n == len(targets):
        # 同序退化：仅在数量吻合时允许，并在调用方打印警告
        return list(range(len(targets)))
    if n == 0:
        raise RuntimeError(
            "无法读取设备通道信息（既没有通道名也没有通道数）。"
            "请在配置里显式给 source.channel_index，例如 "
            f"channel_index: [0, 1, 2, 3, 4, 5, 6, 7]（顺序同 {targets}）。"
        )
    raise RuntimeError(
        f"设备有 {n} 个通道但未发布通道名，无法自动挑出 {len(targets)} 个目标通道 {targets}。\n"
        "修法：在配置里写 source.channel_index，给出这 8 个通道在设备里的下标（顺序同目标顺序）。"
    )


class LSLSource(Source):
    def __init__(
        self,
        stream_name: str = "",
        sfreq: float = 250.0,
        ch_names: Sequence[str] = (),
        chunk_samples: int = 25,
        resolve_timeout: float = 5.0,
        stream_type: str = "EEG",
        channel_map: Dict[str, str] | None = None,
        channel_index: Sequence[int] | None = None,
    ):
        self.stream_name = (stream_name or "").strip()
        self.stream_type = (stream_type or "EEG").strip()
        self.sfreq = float(sfreq)
        self.ch_names = list(ch_names)
        self.chunk_samples = int(chunk_samples)
        self.resolve_timeout = float(resolve_timeout)
        self.channel_map = dict(channel_map or {})
        self.channel_index = list(channel_index or [])
        self._inlet = None
        self._idx: List[int] = []
        self._device_count = 0
        self._device_labels: List[str] = []
        self.info_line = ""      # 启动后填充，供日志/证据留痕

    # ---- 连接 ----
    def _discover(self):
        from pylsl import resolve_byprop

        if self.stream_name:
            streams = resolve_byprop("name", self.stream_name, timeout=self.resolve_timeout)
            if streams:
                return streams
            # 名字没命中 → 退化为按类型发现，并提示
            print(
                f"[lsl] 未找到名为 {self.stream_name!r} 的流，改为按 type={self.stream_type!r} 发现。"
            )
        streams = resolve_byprop("type", self.stream_type, timeout=self.resolve_timeout)
        if not streams:
            raise RuntimeError(
                f"{self.resolve_timeout}s 内没有发现 type={self.stream_type!r} 的 LSL 流。\n"
                "检查：采集软件是否已启动并开始发布；防火墙是否放行；"
                "必要时改用 name 精确指定（source.stream_name）。"
            )
        if len(streams) > 1:
            print(f"[lsl] 发现 {len(streams)} 个候选流，使用第一个：")
            for s in streams:
                i = s
                print(
                    f"      name={i.name()!r} type={i.type()!r} "
                    f"ch={i.channel_count()} sfreq={i.nominal_srate()}"
                )
        return streams

    def start(self) -> None:
        try:
            from pylsl import StreamInlet
        except ImportError as e:  # pragma: no cover
            raise RuntimeError(
                "未安装 pylsl。请执行：pip install pylsl\n"
                "（Windows 下如安装失败，可装 conda-forge 的 liblsl 后重试）"
            ) from e

        streams = self._discover()
        stream = streams[0]
        self._inlet = StreamInlet(stream, max_buflen=360)

        # 采样率以设备为准，避免配置错误导致时间戳/窗口漂移
        try:
            info = self._inlet.info()
            self.sfreq = float(info.nominal_srate())
            self._device_count = int(info.channel_count())
            self._device_labels = channel_labels_of(info)
        except Exception:  # pragma: no cover
            pass

        if self._device_count and len(self.ch_names) and self._device_count < len(self.ch_names):
            raise RuntimeError(
                f"设备只有 {self._device_count} 个通道，少于项目需要的 {len(self.ch_names)} 个："
                f"{self.ch_names}"
            )

        self._idx = resolve_index_map(
            targets=self.ch_names,
            device_labels=self._device_labels,
            channel_map=self.channel_map,
            channel_index=self.channel_index,
            device_count=self._device_count or None,
        )

        how = (
            "channel_index" if self.channel_index
            else ("channel_map" if self.channel_map else ("name" if self._device_labels else "same-order"))
        )
        self.info_line = (
            f"[lsl] stream={stream.name()!r} type={stream.type()!r} "
            f"sfreq={self.sfreq:g} device_ch={self._device_count} "
            f"labels={self._device_labels or 'none'} map_by={how} -> idx={self._idx}"
        )
        print(self.info_line)
        if how == "same-order":
            print("[lsl][WARN] 设备未发布通道名，按通道数相同假定顺序一致；"
                  "若输出左右相反，请用 channel_index 显式指定。")

    # ---- 数据 ----
    def stream(self) -> Iterator[EEGChunk]:
        if self._inlet is None:
            self.start()
        n_target = len(self.ch_names)
        while True:
            samples, ts = self._inlet.pull_chunk(
                timeout=1.0, max_samples=self.chunk_samples
            )
            if not samples:
                continue
            arr = np.asarray(samples, dtype=np.float64).T   # (n_dev, n_samples)
            if self._idx and arr.shape[0] != self._device_count:
                raise RuntimeError(
                    f"设备通道数发生变化：启动时 {self._device_count}，当前 {arr.shape[0]}。"
                    "请重新连接。"
                )
            if self._idx:
                arr = arr[self._idx, :]
            elif arr.shape[0] != n_target:
                raise RuntimeError(
                    f"数据块通道数 {arr.shape[0]} 与目标 {n_target} 不一致，且未完成映射。"
                )
            yield EEGChunk(
                data=arr,
                sfreq=self.sfreq,
                t0=float(ts[0]),
                ch_names=self.ch_names,
            )

    def stop(self) -> None:
        self._inlet = None
