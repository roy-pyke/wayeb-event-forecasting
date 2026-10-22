"""Delayed-feedback expert aggregation with an exploration floor.

    A single convex weight vector combines all horizons, retaining CDF ordering.
    Runtime weights only see feedback explicitly delivered by the caller.
"""
import heapq
import numpy as np


class DelayedExpertMixer:
    def __init__(self, experts=2, eta=2.0, share=0.02):
        if experts < 1 or eta <= 0 or not 0 <= share < 1:
            raise ValueError("invalid expert aggregation parameters")
        self.weights = np.ones(experts) / experts
        self.eta, self.share = eta, share
        self.last_information_time = -float("inf")
        self.updates = 0

    def predict(self, predictions):
        predictions = np.asarray(predictions)
        if predictions.shape[0] != len(self.weights):
            raise ValueError("expert shape mismatch")
        return self.weights @ predictions

    def observe(self, probabilities, outcome, information_time, now):
        if information_time > now or information_time < self.last_information_time:
            raise ValueError("feedback must arrive causally and in order")
        if outcome not in (0, 1):
            raise ValueError("binary feedback required")
        loss = (np.asarray(probabilities) - outcome)**2
        posterior = self.weights * np.exp(-self.eta * loss)
        posterior /= posterior.sum()
        self.weights = (1 - self.share) * posterior + self.share / len(posterior)
        self.last_information_time = information_time
        self.updates += 1


def causal_mix(data, baseline, context, horizons, eta=2.0, share=0.02):
    """Evaluation scheduler knows labels, but releases them only when observable.

    Positive: at observed completion. Negative: at horizon end. An unobserved
    censored horizon produces no feedback. The mixer itself never sees residuals.
    """
    mixer = DelayedExpertMixer(2, eta, share)
    queue, count = [], 0
    mixed = np.zeros_like(baseline)
    weights = np.zeros((len(baseline), 2))
    feedback_audit = {"updates": 0, "early_feedback": 0, "eta": eta, "share": share}
    # stable chronological order allows interleaved instances
    for i in np.argsort(data["time"], kind="stable"):
        now = data["time"][i]
        while queue and queue[0][0] <= now:
            available, _, probabilities, outcome = heapq.heappop(queue)
            mixer.observe(probabilities, outcome, available, now)
            feedback_audit["early_feedback"] += int(available > now)
        p = np.stack([baseline[i], context[i]])
        weights[i] = mixer.weights
        mixed[i] = mixer.predict(p)
        for k, horizon in enumerate(horizons):
            remaining, observed = data["residual"][i], data["observed"][i]
            if observed and remaining <= horizon:
                available, y = now+remaining, 1
            elif remaining >= horizon:
                available, y = now+horizon, 0
            else:
                continue
            count += 1
            heapq.heappush(queue, (available, count, p[:, k], y))
    feedback_audit["updates"] = mixer.updates
    feedback_audit["remaining_pending"] = len(queue)
    feedback_audit["mean_context_weight"] = float(np.mean(weights[:, 1]))
    return mixed, weights, feedback_audit
