from collections import defaultdict


def abstract_partition(mon, frontier, policy):
    groups = defaultdict(list)
    for node in frontier:
        if policy == 'known_bits':
            key = node.state[3]
        elif policy == 'monitor_state':
            key = node.state
        elif policy == 'marginal_support':
            codes = mon.codes(node.state)
            lower, upper = codes[0], codes[0]
            for c in codes:
                lower &= c
                upper |= c
            key = (lower, upper)
        else:
            raise ValueError(policy)
        groups[key].append(node)
    return list(groups.values())


def abstract_pooled(source, mon, q, budget, rng, policy):
    # Sequential audit processes only; keep the registered estimator unchanged.
    import pooling
    previous = pooling.partition
    try:
        pooling.partition = lambda m, f, _: abstract_partition(m, f, policy)
        return pooling.pooled(source, mon, q, budget, rng, policy)
    finally:
        pooling.partition = previous
