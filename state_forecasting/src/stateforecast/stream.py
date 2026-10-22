"""Causal stream primitives: recognition and telemetry have separate state."""
from collections import deque
from dataclasses import dataclass, field
import numpy as np


@dataclass(frozen=True)
class Event:
    instance: str
    kind: str
    event_time: float
    arrival_time: float
    values: tuple = ()


class WayebMonitor:
    """Execute a finite type-only transition table exported by the author engine.

    Deliberately not a general register/symbolic/time-window automaton interpreter.
    """
    def __init__(self, table):
        if table["scope"] != "type-only-dsfa-no-window":
            raise ValueError("unsupported automaton scope")
        self.table = table
        self.states = {}
        self.matches = []

    def accept(self, event):
        if event.kind not in self.table["alphabet"]:
            return False  # alpha removes telemetry without advancing the clock
        q = self.states.get(event.instance, self.table["start"])
        q = self.table["transitions"][str(q)][event.kind]
        self.states[event.instance] = q
        matched = q in self.table["finals"]
        if matched:
            self.matches.append((event.instance, event.event_time))
        return matched


@dataclass
class ContextState:
    """Reports are delivered in arrival order; old event-time reports are ignored."""
    width: int
    reports: deque = field(default_factory=lambda: deque(maxlen=4))
    last_arrival: float = -float("inf")

    def accept(self, event):
        if event.event_time > event.arrival_time:
            raise ValueError("event time is later than arrival time")
        if event.arrival_time < self.last_arrival:
            raise ValueError("deliver reports in arrival order")
        if len(event.values) != self.width:
            raise ValueError("sensor schema mismatch")
        self.last_arrival = event.arrival_time
        if self.reports and event.event_time <= self.reports[-1].event_time:
            return False
        self.reports.append(event)
        return True

    def snapshot(self, now):
        if self.last_arrival > now:
            raise ValueError("cannot query history using a future-mutated state")
        if not self.reports:
            return np.full(2 * self.width, np.nan), float("inf")
        current, previous = self.reports[-1], self.reports[0]
        x = np.asarray(current.values, dtype=float)
        dt = current.event_time - previous.event_time
        slope = (x - np.asarray(previous.values)) / dt if dt > 0 else np.zeros(self.width)
        return np.r_[x, slope], now - current.event_time


class Milestones:
    """At-most-once threshold crossings, reported at observation time, not backdated."""
    def __init__(self, thresholds=(0.25, 0.5, 0.75)):
        self.thresholds = tuple(sorted(thresholds))
        self.seen = set()
        self.previous = 0.0

    def update(self, progress, arrival_time):
        crossed = [(h, arrival_time) for h in self.thresholds
                   if self.previous < h <= progress and h not in self.seen]
        self.seen.update(h for h, _ in crossed)
        self.previous = progress
        return crossed

    def reset(self):
        self.seen.clear()
        self.previous = 0.0
