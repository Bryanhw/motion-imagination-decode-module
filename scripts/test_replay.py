"""Small checks for block order, one-shot predictions and message fields."""
import unittest

import numpy as np

from replay_edf import Block, StreamDecoder


class ConstantModel:
    def predict(self, X):
        assert X.shape == (1, 2, 4)
        return np.array([0])


class ReplayChecks(unittest.TestCase):
    def setUp(self):
        self.metadata = {
            "sfreq_hz": 4.0,
            "channel_names": ["C3", "C4"],
            "filter": {"kind": "causal Butterworth SOS bandpass",
                       "initial_state": "zeros per recording", "low_high_hz": [0.2, 1.0], "order": 2},
            "epoch_seconds_after_cue": [1.0, 2.0],
            "epoch_samples": 4,
        }

    def test_one_prediction_after_complete_window(self):
        decoder = StreamDecoder(ConstantModel(), self.metadata, [0])
        self.assertEqual(decoder.feed(Block(0, 4, np.ones((2, 4))))[1], [])
        _, emitted = decoder.feed(Block(4, 8, np.ones((2, 4))))
        self.assertEqual(len(emitted), 1)
        message, detail = emitted[0]
        self.assertEqual(message, {"version": 1, "sequence": 0, "intent": "LEFT_HAND",
                                   "source": "replay", "timestamp": 2.0})
        self.assertEqual(detail["window_start_s"], 1.0)
        self.assertEqual(decoder.feed(Block(8, 12, np.ones((2, 4))))[1], [])

    def test_reject_duplicate_or_missing_block(self):
        decoder = StreamDecoder(ConstantModel(), self.metadata, [0])
        decoder.feed(Block(0, 4, np.ones((2, 4))))
        for bad_start in (0, 5):
            with self.subTest(bad_start=bad_start):
                with self.assertRaisesRegex(ValueError, "丢失、重复或乱序"):
                    decoder.feed(Block(bad_start, bad_start + 4, np.ones((2, 4))))


if __name__ == "__main__":
    unittest.main()
