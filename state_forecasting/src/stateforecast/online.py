"""Executable dual-stream sidecar. Telemetry can refresh forecasts without a match."""
from collections import deque
from dataclasses import dataclass, field
import numpy as np
from .data import BASE, SENSORS
from .stream import ContextState, WayebMonitor
from .model import ReliableForecaster


@dataclass
class Instance:
    started: float | None = None
    context: ContextState = field(default_factory=lambda: ContextState(len(SENSORS)))
    history: deque = field(default_factory=lambda: deque(maxlen=3))
    last_arrival: float = -float("inf")


class StateSidecar:
    def __init__(self, table, context_model, baseline, horizons=(30, 60, 120), stale_after=30):
        self.monitor = WayebMonitor(table)
        self.forecaster = ReliableForecaster(context_model, baseline, stale_after)
        self.horizons = list(horizons)
        self.instances = {}

    def accept(self, event):
        state = self.instances.setdefault(event.instance, Instance())
        if event.arrival_time < state.last_arrival or event.event_time > event.arrival_time:
            raise ValueError("events must arrive causally")
        state.last_arrival = event.arrival_time
        matched = self.monitor.accept(event)
        if event.kind == "LoadStart":
            state.started = event.event_time
            state.context = ContextState(len(SENSORS))
        elif event.kind in {"LoadEnd", "Gap"}:
            if matched and state.started is not None:
                state.history.append(event.event_time - state.started)
            state.started = None
            state.context = ContextState(len(SENSORS))
        elif event.kind == "Telemetry" and state.started is not None:
            state.context.accept(event)
        return matched

    def features(self, instance, now):
        state = self.instances[instance]
        if now < state.last_arrival:
            raise ValueError("cannot query before last arrival")
        if state.started is None:
            return None
        z, fresh = state.context.snapshot(now)
        phase = 2 * np.pi * (now % 86400) / 86400
        base = [now-state.started, state.history[-1] if state.history else np.nan,
                np.mean(state.history) if state.history else np.nan, np.sin(phase), np.cos(phase)]
        return np.r_[base, z, fresh][None, :]

    def predict(self, instance, now):
        x = self.features(instance, now)
        if x is None:
            return None
        probability, fallback = self.forecaster.predict_cdf(x, self.horizons)
        return {"instance": instance, "as_of": now,
                "pattern_state": self.monitor.states[instance],
                "horizons_seconds": self.horizons, "completion_probability": probability[0].tolist(),
                "source": "business_history_fallback" if fallback[0] else "context",
                "report_age_seconds": float(x[0, -1])}
