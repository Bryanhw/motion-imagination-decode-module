"""环形缓冲区单元测试：验证覆盖、取数、时间戳的正确性。"""

import numpy as np

from bci_decoder.buffer import RingBuffer


def test_append_and_get_last():
    rb = RingBuffer(n_channels=2, capacity=10, sfreq=10.0)
    rb.append(np.arange(8).reshape(2, 4), t0=0.0)
    assert rb.total == 4
    got = rb.get_last(4)
    assert got.shape == (2, 4)
    assert np.array_equal(got[:, 0], np.array([0, 4]))


def test_wraparound_overwrites_oldest():
    rb = RingBuffer(n_channels=1, capacity=5, sfreq=10.0)
    rb.append(np.arange(8).reshape(1, 8), t0=0.0)
    assert rb.total == 8
    assert rb.filled == 5
    got = rb.get_last(5)
    assert np.array_equal(got[0], np.array([3, 4, 5, 6, 7]))


def test_get_last_more_than_available():
    rb = RingBuffer(n_channels=1, capacity=5, sfreq=10.0)
    rb.append(np.arange(3).reshape(1, 3), t0=0.0)
    got = rb.get_last(10)
    assert got.shape == (1, 3)


def test_timestamps():
    rb = RingBuffer(n_channels=1, capacity=100, sfreq=10.0)
    rb.append(np.zeros((1, 20)), t0=5.0)
    assert abs(rb.latest_time() - (5.0 + 19 / 10.0)) < 1e-9
    assert abs(rb.window_start_time(10) - (5.0 + 10 / 10.0)) < 1e-9


def test_channel_mismatch_raises():
    rb = RingBuffer(n_channels=2, capacity=10, sfreq=10.0)
    try:
        rb.append(np.zeros((3, 5)))
    except ValueError:
        return
    raise AssertionError("通道数不匹配时应抛 ValueError")
