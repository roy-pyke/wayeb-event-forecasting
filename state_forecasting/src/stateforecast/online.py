"""Executable dual-stream sidecar. Telemetry can refresh forecasts without a match."""
from collections import deque
from dataclasses import dataclass, field
import numpy as np
from .data import BASE, SENSORS
from .stream import ContextState, WayebMonitor
from .model import ReliableForecaster
from .mixer import DelayedExpertMixer


@dataclass
class Instance:
    started: float | None = None
    context: ContextState = field(default_factory=lambda: ContextState(len(SENSORS)))
    history: deque = field(default_factory=lambda: deque(maxlen=3))
    last_arrival: float = -float("inf")


class StateSidecar:
    def __init__(self, table, context_model, baseline, horizons=(30, 60, 120), stale_after=30, adaptive=True):
        self.monitor = WayebMonitor(table)
        self.forecaster = ReliableForecaster(context_model, baseline, stale_after)
        self.horizons = list(horizons)
        self.instances = {}
        self.mixer = DelayedExpertMixer() if adaptive else None
        self.pending = []
        self.clock = -float("inf")

    def _advance(self, now, inclusive=True):
        if now < self.clock:
            raise ValueError("the sidecar's global arrival clock cannot go backwards")
        self.clock = now
        if self.mixer is None:
            return
        ready = [p for p in self.pending if p['deadline'] < now or (inclusive and p['deadline'] == now)]
        for p in sorted(ready, key=lambda p: p['deadline']):
            self.mixer.observe(p['experts'], 0, p['deadline'], now)
            p['done'] = True
        self.pending = [p for p in self.pending if not p['done']]

    def accept(self, event):
        if event.kind in self.monitor.table['alphabet'] and event.event_time != event.arrival_time:
            raise ValueError("late business events require a watermark policy; only telemetry may be delayed")
        self._advance(event.arrival_time, inclusive=False)
        state = self.instances.setdefault(event.instance, Instance())
        if event.arrival_time < state.last_arrival or event.event_time > event.arrival_time:
            raise ValueError("events must arrive causally")
        state.last_arrival = event.arrival_time
        matched = self.monitor.accept(event)
        if event.kind == "LoadStart":
            state.started = event.event_time
            state.context = ContextState(len(SENSORS))
        elif event.kind in {"LoadEnd", "Gap"}:
            if self.mixer is not None:
                for p in self.pending:
                    if p['instance'] == event.instance:
                        if matched:
                            self.mixer.observe(p['experts'], 1, event.arrival_time, event.arrival_time)
                        p['done'] = True  # Gap censors: never turn unknown labels into negatives
                self.pending = [p for p in self.pending if not p['done']]
            if matched and state.started is not None:
                state.history.append(event.event_time - state.started)
            state.started = None
            state.context = ContextState(len(SENSORS))
        elif event.kind == "Telemetry" and state.started is not None:
            state.context.accept(event)
        self._advance(event.arrival_time)
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
        self._advance(now)
        x = self.features(instance, now)
        if x is None:
            return None
        probability, fallback = self.forecaster.predict_cdf(x, self.horizons)
        context_weight = 1.0
        if self.mixer is not None:
            baseline = self.forecaster.baseline.predict_cdf(x, self.horizons)[0]
            experts = np.stack([baseline, probability[0]])
            context_weight = float(self.mixer.weights[1])
            probability = self.mixer.predict(experts)[None, :]
            for j,h in enumerate(self.horizons):
                self.pending.append(dict(instance=instance, deadline=now+h, experts=experts[:,j], done=False))
        return {"instance": instance, "as_of": now,
                "pattern_state": self.monitor.states[instance],
                "horizons_seconds": self.horizons, "completion_probability": probability[0].tolist(),
                "source": "business_history_fallback" if fallback[0] else "context",
                "context_expert_weight": context_weight,
                "report_age_seconds": float(x[0, -1])}
