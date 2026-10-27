"""通道映射解析的单元测试（不依赖 pylsl / 真实设备）。

覆盖：名称直配、别名映射、显式索引、缺通道报错、无通道名退化、越界/重复校验。
通道顺序错会让左右输出稳定相反（红线 4），所以这些分支必须有测试兜住。
"""

from __future__ import annotations

import pytest

from bci_decoder.config import DEFAULT_CH_NAMES
from bci_decoder.sources.lsl import resolve_index_map

T = list(DEFAULT_CH_NAMES)


def test_same_name_direct_match():
    labels = ["C3", "Cz", "C4", "CP3", "CP4", "P3", "P4", "Oz"]
    assert resolve_index_map(T, labels) == [0, 1, 2, 3, 4, 5, 6, 7]


def test_same_name_shuffled_device_order():
    labels = ["Oz", "P4", "P3", "CP4", "CP3", "C4", "Cz", "C3"]
    idx = resolve_index_map(T, labels)
    assert [labels[i] for i in idx] == T


def test_channel_map_alias():
    labels = ["EEG_C3", "EEG_Cz", "EEG_C4", "EEG_CP3", "EEG_CP4", "EEG_P3", "EEG_P4", "EEG_Oz"]
    cmap = {lab: tgt for lab, tgt in zip(labels, T)}
    idx = resolve_index_map(T, labels, channel_map=cmap)
    assert [cmap[labels[i]] for i in idx] == T


def test_channel_map_when_device_has_extra_channels():
    labels = ["Fp1", "EEG_C3", "EEG_Cz", "EEG_C4", "EEG_CP3", "EEG_CP4",
              "EEG_P3", "EEG_P4", "EEG_Oz", "Fp2"]
    cmap = {lab: tgt for lab, tgt in zip(labels[1:9], T)}
    idx = resolve_index_map(T, labels, channel_map=cmap)
    assert [cmap[labels[i]] for i in idx] == T


def test_channel_index_explicit():
    labels = ["Fp1", "Fp2", "C3", "Cz", "C4", "CP3", "CP4", "P3", "P4", "Oz"]
    idx = resolve_index_map(T, labels, channel_index=[2, 3, 4, 5, 6, 7, 8, 9])
    assert [labels[i] for i in idx] == T


def test_channel_index_beats_map():
    labels = ["A", "B", "C", "D", "E", "F", "G", "H"]
    idx = resolve_index_map(T, labels, channel_map={}, channel_index=list(range(8)))
    assert idx == list(range(8))


def test_missing_channel_raises_with_device_list():
    labels = ["C3", "Cz", "C4", "CP3", "CP4", "P3", "P4"]  # 少 Oz
    with pytest.raises(RuntimeError) as e:
        resolve_index_map(T, labels)
    msg = str(e.value)
    assert "Oz" in msg
    assert "C3" in msg  # 打印了设备实际通道


def test_no_labels_same_count_falls_back_to_order():
    assert resolve_index_map(T, [], device_count=8) == list(range(8))


def test_no_labels_wrong_count_raises():
    with pytest.raises(RuntimeError) as e:
        resolve_index_map(T, [], device_count=32)
    assert "channel_index" in str(e.value)


def test_no_info_at_all_raises():
    with pytest.raises(RuntimeError):
        resolve_index_map(T, [], device_count=0)


def test_channel_index_length_mismatch():
    with pytest.raises(RuntimeError):
        resolve_index_map(T, [], channel_index=[0, 1, 2])


def test_channel_index_out_of_range():
    with pytest.raises(RuntimeError):
        resolve_index_map(T, [], channel_index=[0, 1, 2, 3, 4, 5, 6, 99], device_count=8)


def test_channel_index_duplicates():
    with pytest.raises(RuntimeError):
        resolve_index_map(T, [], channel_index=[0, 1, 2, 3, 4, 5, 6, 6], device_count=8)


def test_case_insensitive_match():
    labels = ["c3", "CZ", "C4", "cp3", "CP4", "p3", "P4", "oz"]
    assert [labels[i].lower() for i in resolve_index_map(T, labels)] == [t.lower() for t in T]
