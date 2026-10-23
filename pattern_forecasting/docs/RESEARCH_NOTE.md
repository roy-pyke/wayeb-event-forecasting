# When Semantic Structure Does Not Translate into Communication Savings

## A reproducible study of complex-event forecast messages

**Status: research draft for discussion.** This manuscript reports failed superiority hypotheses and bounded empirical findings. It is not a claim of established algorithmic novelty or submission readiness. Its companion [claim audit](PAPER_READINESS.md) records the unresolved contribution boundary. All figures and numerical tables can be rebuilt from public reports.

## Abstract

Complex-event forecasts are logically related: a pattern may imply another, alternative endpoints may be mutually exclusive within a short horizon, and future completion probabilities must agree with the current execution automaton. We investigate whether these relations produce useful communication savings when remote forecasts already benefit from strong numerical compression. We implement an automaton-based feasible-outcome oracle, exact and greedy coordinate refresh, state-dependent probability-coordinate reconstruction, and an application of classical online safe-set tracking to shared forecast codebooks. Comparators share information, forecasting models, probability coherence, loss certificates, quantization, sparse updates, and message headers. Across three complex-pattern families and independent future-year evaluations in air quality and household electricity, the registered superiority gates are not met. In the primary frozen comparison, state-dependent coordinates save 0.34% and 0.64% of application bytes, with paired weekly intervals including zero. Mean Brier scores improve slightly. A subsequent registered codebook experiment is also defeated on communication by a simple history-based selector. We provide an exact counterexample separating pointwise certificate dominance from closed-loop packet dominance, while acknowledging prior warnings about this phenomenon in event-triggered control. The artifact documents the practical limits of these mechanisms under the evaluated workloads and cost model.

## 1. Question and scope

The question is not whether continuous context can aid prediction. Attribute-aware monitoring and dynamic time-to-event models already address that broader idea. We instead ask whether known relations among event queries produce an additional, measurable benefit for communicating forecasts when basic compression techniques are already available.

We preserve every business event delivered to the recognizer. A full-context forecaster runs at the sending endpoint on every query. An auxiliary message updates the remote forecast only when necessary under a loss-degradation contract. Thus communication is the resource of interest; neither sensing nor inference energy is saved by construction. Our experiments count serialized application messages, not full network traffic or radio energy.

The target is the first strictly future reported matching endpoint of each streaming pattern within several physical-time horizons. It is not the completion of an anchored business case. Public sensor signals are converted into business symbols by training-only rules. These research targets are not externally labeled accidents or failures.

## 2. Feasible outcomes and score certificates

Let q be the common execution state of P pattern automata. For K horizons, write a joint cumulative completion label as `y∈{0,1}^{d}`, `d=PK`. Let `Y_q` contain all labels reachable by an allowed future symbol stream. Silence is allowed, and at most one business event occurs per native sample. The execution semantics, including reset after a match, are part of the automaton definition.

For a cached forecast p and a full-context reference f, mean Brier loss satisfies

`L(p,y)−L(f,y) = (||p||²−||f||²−2y·(p−f))/d`.

Consequently,

`C_q(p,f) = (||p||²−||f||² + max_{y∈Y_q} −2y·(p−f))/d`

is an exact worst-case excess over the enumerated feasible outcomes. Testing `C_q≤ε` does not require the future realized label. The guarantee is conditional on correct shared business state, consistent model identity, causal ordering, and delivery of a triggered message before the scored query. It does not certify f itself or establish calibration.

We compute support values by a max-plus dynamic program over the joint automaton and a bit mask of patterns already completed. Horizon boundaries accumulate the appropriate label coordinates. A witness version reconstructs a maximizing future label. This is a standard weighted-automaton optimization construction, not a claim of a new max-plus algebra.

A semantic pitfall matters operationally. Language inclusion does not automatically imply inclusion of *reported endpoints* when each recognizer resets independently after a match. An `ABABD` example exposed this issue during development. The directional family was explicitly recompiled with overlap semantics and revalidated before fitting its predictors. Every asserted relation is checked on the execution automata, not inferred solely from regular-language notation.

## 3. Four tested mechanisms

### 3.1 Joint trigger and sparse coordinate refresh

The first candidate replaces independent or per-pattern monotone outcome sets by `Y_q`. A strong static comparator already includes every time-unbounded joint Boolean relation. Pointwise tightening was rare or small in the evaluated streams. A second candidate enumerates the 512 subsets of nine coordinates to minimize each current refresh, compared with greedy magnitude and certificate-gain choices given the same loss oracle. Its gains did not meet the registered gate. Myopic minimality is not a statement about the subsequent cache trajectory.

### 3.2 State-dependent independent coordinates

Place feasible labels in a matrix Y. Because future silence is possible, zero belongs to Y and the affine hull is a linear subspace. Choose independent columns I and a matrix B satisfying `Y[:,I]B=Y`. Every coherent forecast `f=λᵀY` then satisfies `f=f_I B`. The rank is the minimal dimension for exact *linear* encoding and reconstruction on this set. These are elementary linear-algebra facts; predictive state representations and belief compression provide direct prior art for probability-coordinate reduction.

An alternative compiler discovers the label span using support-oracle witnesses. Starting from zero, maximize both signs of each orthogonal-complement basis direction. A nonzero witness increases rank. If none exists, the current span contains all feasible labels. In exact arithmetic, at most `d(d+1)` support calls suffice. Numerical rank thresholds are disclosed and checked against explicit enumeration on the experimental families. The product state space and completion masks can still grow exponentially, and the runtime coherence projection still uses an explicit convex hull. We make no end-to-end scalability claim for unrestricted pattern collections.

All representations share Euclidean coherence repair, actual 8/16-bit quantization and float32/64 fallbacks, greedy partial refresh, and the exact loss certificate on the *decoded* forecast. The full-coordinate baseline is also equivalent to the compiled static-coordinate representation in the measured configurations. A current-state zero-omission comparator isolates rank reductions beyond impossible coordinates. Message headers occupy 27 bytes, plus two bytes for a sparse mask when used.

### 3.3 Safe codebook tracking

Following the negative coordinate results, we registered a separate candidate. A shared 64-entry codebook is fitted to training-period full forecasts. Codeword j is decoded as the projection of its persistent original vector onto the current state's feasible polytope. Define the safe index set by `C_q(g(q,j),f_t)≤ε`.

The candidate maintains the intersection of safe sets within a phase and samples uniformly from surviving indices when the current choice is eliminated. This is the classical uniform metrical-service-system strategy. On a fixed nonempty request sequence, its expected switching cost is at most `H_M(OPT+1)` under a unit index-switch metric. This follows from the harmonic elimination bound within each phase and an offline switch required between consecutive maximal phases. It is not a new competitive-analysis result, nor does it compare against arbitrary continuous forecasts or variable-length codecs.

An uncovered query invokes a common full-forecast fallback. The competitive statement is restricted to covered runs; fallback and re-entry overhead are charged in the experiments. A 28-byte index frame includes the same metadata header. Comparators retain a safe current index and then choose the nearest forecast, the smallest current certificate, a uniformly random current-safe index, or the index minimizing the worst certificate over the last 4 or 16 queries. They use no future labels. The offline dynamic-programming optimum is reported only as a diagnostic lower bound.

## 4. Experimental protocol

Three families cover nested loops, directional/overlapping queries, and multi-sensor alternative endpoints. Their reachable product automata contain 11, 15, and 6 states. Thirty-six comparisons against the authors' Wayeb command-line recognizer, using random and real event streams, produce zero endpoint mismatches. Separate label audits find no infeasible fully observed confirmation labels.

The principal independent domains are Beijing air quality and household electricity. Air training uses six stations in March 2013–September 2014; calibration uses the rest of 2014, development uses 2015, and frozen confirmation uses 2016 at twelve stations. Six confirmation stations were absent from training. Electricity uses January–September 2007 for training, the rest of 2007 for calibration, 2008 for development, and 2009 for confirmation. MetroPT 2020 is an already-exposed diagnostic dataset; its sparse multi-sensor matches cannot substantiate generalization or useful fault forecasting.

Short horizons are one, two, and three native samples: hours for air and minutes for electricity. Query spacing remains hourly and five-minute respectively. Missing observations cut coverage and execution segments. Unknown future outcomes are censored, not labeled negative. The experiment shares current business metadata, state, and eight-sample telemetry histories across histogram gradient boosting, extra trees, and an attentive GRU event-time model. Each model sees the same sampled training queries and cache-age augmentation. Calibration and model selection use separate calibration and development periods.

Three predictor seeds are evaluated for the main multi-sensor family. The original confirmation evaluates a frozen diagnostic hypothesis after development gates had failed; it is not a fresh positive-success test. The later codebook experiment uses five random policy seeds on development only. Air 2017 and electricity 2010 remain untouched reserves.

We aggregate uncertainty by Monday-aligned recorded-clock calendar weeks, keeping all stations in a week together, and use 1,000 paired bootstrap replicates. Intervals are pointwise 95%; query count is not the number of independent statistical units. Seed variability is reported separately.

## 5. Findings

All detailed, automatically rebuilt tables appear in [RESULTS](RESULTS.md); JSON cluster sums remain available for reanalysis.

| Frozen primary comparison, ε=.002 | Full-coordinate bytes/query | Independent-coordinate bytes/query | Relative saving, paired 95% interval |
|---|---:|---:|---:|
| Air 2016 | 7.518 | 7.493 | 0.34% [−0.32%, 1.00%] |
| Electricity 2009 | 10.795 | 10.726 | 0.64% [−1.18%, 2.37%] |

The registered 5% gate fails. Other seeds do not justify replacing the primary choice. Candidate mean Brier differences are −0.000187 and −0.000306, corresponding to approximately 1.05% and 1.51% of the baseline's *overall* Brier, not a large improvement in total predictive accuracy. There are zero observed certificate or tolerance violations among 199,555 fully scored primary confirmation queries. This empirical check does not broaden the delivery assumptions.

The multi-sensor short-horizon label ranks are 2/4/6 while nonzero coordinate counts are 3/6/9. This algebraic reduction does not survive as a comparable total-byte reduction. Headers, existing quantization and partial refresh, and changed future cache histories all matter. The directional negative control has rank equal to its nonzero-coordinate count, and its zero-omission and independent-coordinate codecs give identical results.

The later codebook test also fails its registered mechanism gate. Five-seed phase-policy means are 6.460 and 8.111 bytes/query; the strongest same-codebook history selector uses 6.095 and 7.931. The candidate consumes 5.98% and 2.27% more bytes, while having lower Brier loss. Relative to memoryless uniform selection, phase intersections save only 1.19% and 1.50%. The approximately 89% codebook coverage leaves common fallback traffic responsible for 47%–59% of candidate bytes. Ordinary codebook compression explains much of the gain over the original coordinate codec and must not be credited to a novel phase mechanism.

## 6. An exact separation between pointwise and closed-loop guarantees

Let `S={(0,0),(1,0),(0,1)}` and `W=S∪{(1,1)}`. Then `C_S(p,f)≤C_W(p,f)` for every common cache/reference pair. With ε=.1 and initial cache `(.29,.43)`, consider references

`(.16,.48), (.41,.48), (.42,.24), (.11,.44)`.

The S policy skips the first two, then transmits twice. The W policy transmits only the second reference and retains it. Alternating the last two references forces S to keep transmitting while W never transmits again. All reference vectors belong to `conv(S)`. The exact certificate values and Fraction-arithmetic checks are in [CLOSED_LOOP](CLOSED_LOOP.md). The packet ratio can therefore be arbitrarily large even though the tighter certificate is pointwise dominant. This falsifies a tempting inference about this cache-update scheme.

The general warning is not new: Seidel et al.'s window-based event-triggered consensus paper explicitly notes that a less conservative trigger need not yield fewer closed-loop triggers. Our construction makes the issue directly auditable in this proper-score forecast-message setting. We have not established that this construction is independently novel or sufficient as a theoretical contribution.

## 7. Limitations and implications

The artifact supports bounded empirical findings about these patterns, predictors, horizons and byte costs. It does not show that all semantic compression is ineffective. The pattern languages have only three simultaneous queries, and runtime geometry remains explicit. Network delay, loss, hardware energy and live distributed throughput are not evaluated. The available industrial diagnostic target is sparse, and no claim of operational alarm usefulness is warranted.

The methodological lesson is supported by concrete comparisons: give baselines the same information and standard compression tools; evaluate actual decoded forecasts and actual message lengths; distinguish static from state-dependent constraints; preserve the execution recognizer's semantics; and assess the entire cache trajectory. These controls convert apparently attractive algebraic arguments into falsifiable systems claims. The current evidence does not establish a superior new forecasting or communication method.

## 8. Artifact and provenance

The public [repository](https://github.com/roy-pyke/wayeb-event-forecasting) contains pinned author submodules, new research code, protocols, all compact positive and negative reports, source hashes and reproduction commands. Ninety model files are available in the [research snapshot](https://github.com/roy-pyke/wayeb-event-forecasting/releases/tag/pattern-research-20261022). Download and restoration into an empty directory were verified for every model. An independent CPU refit of the air GRU reproduced 2,000 development predictions bit for bit. Original confirmation sources, models and eventization thresholds still match their frozen identities after later development. Source and publication licences remain separate; this project does not relicense upstream implementations.

## Selected primary references

- [RTCEF / Wayeb runtime adaptation, DEBS 2025](https://cer.iit.demokritos.gr/publications/papers/2025/debs2025.pdf).
- [Dynamic-DeepHit](https://pubmed.ncbi.nlm.nih.gov/30951460/) and [author implementation](https://github.com/chl8856/Dynamic-DeepHit).
- [Predd et al., probabilistic coherence and proper scoring](https://arxiv.org/abs/0710.3183).
- [Predictive Representations of State, NIPS 14](https://proceedings.neurips.cc/paper/2001/file/1e4d36177d71bbb3558e43af9577d70e-Paper.pdf).
- [Poupart and Boutilier, POMDP belief compression, NIPS 2004](https://papers.neurips.cc/paper_files/paper/2004/file/81c2f886f91e18fe16d6f4e865877cb6-Paper.pdf).
- [Solowjow and Trimpe, event-triggered learning](https://doi.org/10.1016/j.automatica.2020.109009).
- [AutoMon, author artifact](https://github.com/hsivan/automon).
- [Bansal et al., competitive algorithms on uniform metrics](https://doi.org/10.1145/3568677).
- [Bubeck and Rabani, parametrized metrical task systems](https://arxiv.org/abs/1904.03874).
- [Seidel et al., window-based periodic event-triggered consensus](https://people.kth.se/~dimos/pdfs/TCNS_Seidel_23.pdf).
