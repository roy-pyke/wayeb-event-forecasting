"""Structural, label-free audit of profile and witness-oracle compilers."""
import time
import numpy as np
from patternforecast.automata import PatternFamily
from patternforecast.affine import CoordinateMap
from patternforecast.oracle import MaxPlusOracle
from patternforecast.common import FAMILY,REPORTS,write_json

family=PatternFamily();oracle=MaxPlusOracle(family.next,family.final)
rows=[]
for horizons in [(1,2,3),(2,4,6),tuple(range(1,13))]:
    for q in range(len(family.states)):
        start=time.perf_counter();mapping,diag=CoordinateMap.compile_from_oracle(oracle,q,horizons)
        oracle_seconds=time.perf_counter()-start
        start=time.perf_counter();y=family.feasible(q,horizons).astype(float)
        enumeration_seconds=time.perf_counter()-start
        error=float(np.max(np.abs(mapping.expand(y[:,mapping.indices])-y)))
        assert error<1e-9
        assert mapping.dimension==np.linalg.matrix_rank(y,tol=1e-10)
        rows.append(dict(q=q,horizons=horizons,rank=mapping.dimension,nonzero=int(y.max(0).sum()),
                         profiles=len(y),oracle_calls=diag['oracle_calls'],oracle_seconds=oracle_seconds,
                         enumeration_seconds=enumeration_seconds,max_reconstruction_error=error,
                         indices=mapping.indices,reconstruct=mapping.reconstruct))
    print(FAMILY,horizons,'verified',len(family.states),flush=True)
write_json(REPORTS/'codec-structure.json',dict(family=FAMILY,rows=rows,
    note='Single local CPU timing, compiler only; not an end-to-end scalability benchmark.'))
