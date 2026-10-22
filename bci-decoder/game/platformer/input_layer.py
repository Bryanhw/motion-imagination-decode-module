"""Versioned intent decisions, adapters, and a single validated input stream."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import time
from typing import Iterable, Iterator

INTENTS = {"LEFT_HAND", "RIGHT_HAND", "NONE"}
SOURCES = {"keyboard", "replay", "device"}


@dataclass(frozen=True)
class Decision:
    version: int
    sequence: int
    intent: str
    source: str
    timestamp: float

    @classmethod
    def parse(cls, value: dict) -> "Decision":
        if not isinstance(value, dict):
            raise ValueError("决策必须是 JSON 对象")
        try:
            decision = cls(
                version=value["version"], sequence=value["sequence"],
                intent=value["intent"], source=value["source"],
                timestamp=value["timestamp"],
            )
        except (KeyError, TypeError) as exc:
            raise ValueError(f"决策缺少必需字段: {exc}") from exc
        if decision.version != 1:
            raise ValueError("仅支持决策契约 version=1")
        if isinstance(decision.sequence, bool) or not isinstance(decision.sequence, int) or decision.sequence < 0:
            raise ValueError("sequence 必须是非负整数")
        if decision.intent not in INTENTS:
            raise ValueError(f"不支持的 intent: {decision.intent!r}")
        if decision.source not in SOURCES:
            raise ValueError(f"不支持的 source: {decision.source!r}")
        if isinstance(decision.timestamp, bool) or not isinstance(decision.timestamp, (int, float)):
            raise ValueError("timestamp 必须是数字")
        return decision

    def to_dict(self) -> dict:
        return {"version": self.version, "sequence": self.sequence,
                "intent": self.intent, "source": self.source,
                "timestamp": self.timestamp}


@dataclass(frozen=True)
class InputState:
    intent: str = "NONE"
    source: str = "keyboard"
    received_at: float = 0.0
    sequence: int = -1


class DecisionReceiver:
    """Validate decisions, ignore stale sequence numbers, and expire remote input."""

    def __init__(self, timeout: float = 1.5):
        if timeout <= 0:
            raise ValueError("timeout 必须大于 0")
        self.timeout = timeout
        self.state = InputState()
        self.last_sequence: dict[str, int] = {}

    def receive(self, decision: Decision | dict, received_at: float | None = None) -> bool:
        message = decision if isinstance(decision, Decision) else Decision.parse(decision)
        previous = self.last_sequence.get(message.source, -1)
        if message.sequence <= previous:
            return False
        self.last_sequence[message.source] = message.sequence
        self.state = InputState(message.intent, message.source,
                                time.monotonic() if received_at is None else received_at,
                                message.sequence)
        return True

    def current(self, now: float | None = None) -> InputState:
        state = self.state
        clock = time.monotonic() if now is None else now
        if state.source in {"replay", "device"} and state.intent != "NONE" and clock - state.received_at > self.timeout:
            return InputState("NONE", state.source, state.received_at, state.sequence)
        return state

    def reset_remote(self) -> None:
        """Fail safe on transport loss and allow a restarted sender's sequence."""
        self.state = InputState("NONE", "device", time.monotonic(), -1)
        self.last_sequence.pop("device", None)


class KeyboardInputAdapter:
    """Translate held W and rising D presses into the shared decision stream."""

    def __init__(self):
        self.sequence = 0
        self.previous_d = False
        self.last_intent = "NONE"

    def press_jump(self, timestamp: float | None = None) -> Decision:
        """Capture D's keydown edge immediately, even between polling frames."""
        now = time.monotonic() if timestamp is None else timestamp
        self.previous_d = True
        self.last_intent = "RIGHT_HAND"
        return self._make("RIGHT_HAND", now)

    def poll(self, w_held: bool, d_held: bool, timestamp: float | None = None) -> list[Decision]:
        now = time.monotonic() if timestamp is None else timestamp
        events: list[Decision] = []
        # Emit D's edge alone so the controller sees RIGHT_HAND for one update.
        # The held W/NONE state is emitted on the next poll.
        if d_held and not self.previous_d:
            events.append(self.press_jump(now))
            return events
        intent = "LEFT_HAND" if w_held else "NONE"
        if intent != self.last_intent:
            events.append(self._make(intent, now))
        self.previous_d = d_held
        self.last_intent = intent
        return events

    def _make(self, intent: str, timestamp: float) -> Decision:
        decision = Decision(1, self.sequence, intent, "keyboard", timestamp)
        self.sequence += 1
        return decision


class ReplayInputAdapter:
    """Read one JSONL decision whenever its replay delay has elapsed."""

    def __init__(self, path: str | Path, interval: float = 0.75):
        self.path = Path(path)
        self.interval = interval
        self.decisions = self._read()
        self.index = 0
        self.next_at: float | None = None

    def _read(self) -> list[Decision]:
        decisions = []
        with self.path.open("r", encoding="utf-8") as stream:
            for line_number, line in enumerate(stream, 1):
                if not line.strip() or line.lstrip().startswith("#"):
                    continue
                try:
                    decision = Decision.parse(json.loads(line))
                except (json.JSONDecodeError, ValueError) as exc:
                    raise ValueError(f"{self.path}:{line_number}: {exc}") from exc
                if decision.source != "replay":
                    raise ValueError(f"{self.path}:{line_number}: replay JSONL 的 source 必须是 replay")
                decisions.append(decision)
        for previous, current in zip(decisions, decisions[1:]):
            if current.sequence <= previous.sequence:
                raise ValueError("JSONL sequence 必须严格递增")
        return decisions

    def poll(self, now: float) -> Decision | None:
        if self.index >= len(self.decisions):
            return None
        if self.next_at is not None and now < self.next_at:
            return None
        original = self.decisions[self.index]
        self.index += 1
        self.next_at = now + self.interval
        # Replay timestamps describe recording time; freshness uses this local receipt time.
        return Decision(original.version, original.sequence, original.intent, original.source, now)

    @property
    def finished(self) -> bool:
        return self.index >= len(self.decisions)
