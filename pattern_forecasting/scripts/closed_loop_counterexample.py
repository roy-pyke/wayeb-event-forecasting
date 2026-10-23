"""Exact arithmetic falsification of pointwise-to-closed-loop dominance."""
from fractions import Fraction as F
from patternforecast.common import PACKAGE, write_json

S = [(0, 0), (1, 0), (0, 1)]
W = S + [(1, 1)]
forecasts = [tuple(map(F, row)) for row in [('.29', '.43'), ('.16', '.48'),
             ('.41', '.48'), ('.42', '.24'), ('.11', '.44')]]
epsilon = F(1, 10)


def certificate(p, f, labels):
    return sum(a*a-b*b for a, b in zip(p, f))/2 + max(
        -sum(y*(a-b) for y, a, b in zip(label, p, f)) for label in labels)


def run(sequence):
    cached = [forecasts[0], forecasts[0]]
    counts = [0, 0]
    trace = []
    for i, full in enumerate(sequence, 1):
        assert all(0 <= x <= 1 for x in full) and sum(full) <= 1
        row = dict(t=i, full=[float(x) for x in full])
        for j, (name, labels) in enumerate([('strong', S), ('weak', W)]):
            bound = certificate(cached[j], full, labels)
            send = bound > epsilon
            row.update({f'{name}_bound': str(bound), f'{name}_bound_float': float(bound),
                        f'{name}_send': send})
            if send:
                counts[j] += 1
                cached[j] = full
        trace.append(row)
    return counts, trace


if __name__ == '__main__':
    counts, trace = run(forecasts[1:])
    assert counts == [2, 1]
    reverse = certificate(forecasts[4], forecasts[3], S)
    assert reverse == F('0.29585') > epsilon
    repeated = []
    for repeats in [1, 10, 100, 1000]:
        counts, _ = run(forecasts[1:3] + forecasts[3:5]*repeats)
        assert counts == [2*repeats, 1]
        repeated.append(dict(repeats=repeats, strong_packets=counts[0], weak_packets=counts[1]))
    write_json(PACKAGE/'reports/closed-loop-counterexample.json', dict(
        scope='Exact rational counterexample; not a data or forecast-quality claim',
        epsilon=str(epsilon), forecasts=[[str(x) for x in f] for f in forecasts],
        strong_outcomes=S, weak_outcomes=W, strong_packets=2, weak_packets=1, trace=trace,
        reverse_bound=str(reverse), repeated=repeated,
        conclusion='No finite multiplicative closed-loop packet domination follows from pointwise certificate tightening.'))
    print('exact rational checks passed; repeated packet ratios 2,20,200,2000')
