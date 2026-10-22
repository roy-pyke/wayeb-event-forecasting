# 论文与代码对应 / Literature and implementation map

Sources checked on **2026-10-22**: the [authors' publication list](https://cer.iit.demokritos.gr/publications/), [Wayeb](https://github.com/ElAlev/Wayeb), and the [RTCEF archived release](https://zenodo.org/records/15229227). This is the direct Wayeb/complex-event-forecasting line, not every publication by the three original authors.

| Year | Work and primary source | Relationship and code |
| --- | --- | --- |
| 2017 | Alevizos, Artikis, Paliouras, [Event Forecasting with Pattern Markov Chains](https://doi.org/10.1145/3093742.3093920) ([author PDF](https://cer.iit.demokritos.gr/publications/papers/2017/Forecasting-DEBS17.pdf)) | 起点 / Starting point: regular patterns, finite automata, fixed-order Markov models, first-passage waiting-time distributions and forecast intervals. Current Wayeb's FMM path is its descendant, not an archived copy of the 2017 binary. |
| 2018 | Alevizos, Artikis, Paliouras, [Wayeb: a Tool for Complex Event Forecasting](https://arxiv.org/abs/1901.01826) (LPAR-22, 2018; arXiv upload 2019) | 符号自动机 / Symbolic automata with predicates over event attributes; full-order Markov forecasting. Implemented in Wayeb. |
| 2021/2022 | Alevizos, Artikis, Paliouras, [Complex Event Forecasting with Prediction Suffix Trees](https://arxiv.org/abs/2109.00287) (extended technical report 2021; VLDB Journal 31, 157–180, 2022) | 变阶模型 / Variable-order Markov models using PSTs to retain informative history. Wayeb's `learnSPST` and `forecasting --modelType:vmm` implement this line. |
| 2021 | Alevizos, Artikis, Paliouras, [Symbolic Register Automata for Complex Event Recognition and Forecasting](https://arxiv.org/abs/2110.04032) | 寄存器自动机 / Register automata store past event values. Wayeb includes DSRA support; the author documentation recommends DSFA for the main forecasting route. |
| 2022 | Stavropoulos, Alevizos, Giatrakos, Artikis, [Optimizing Complex Event Forecasting](https://doi.org/10.1145/3524860.3539810) ([author PDF](https://cer.iit.demokritos.gr/publications/papers/2022/debs22.pdf)) | 超参数优化 / Hyperparameter optimisation of forecasting. Related optimisation code is supplied by the later RTCEF project; that does not establish byte-for-byte reproduction of this paper's experiments. |
| 2024 | Alevizos, Artikis, Paliouras, Complex Event Recognition with Symbolic Register Transducers ([authors' list and code link](https://cer.iit.demokritos.gr/publications/)) | 带输出的寄存器转换器 / Symbolic register transducers, an event-recognition extension. The authors link Wayeb. Recognition is distinct from the PST forecasting experiment. |
| 2025 | Pitsikalis, Alevizos, Giatrakos, Artikis, [Run-Time Adaptation of Complex Event Forecasting](https://doi.org/10.1145/3701717.3730539) ([author PDF](https://cer.iit.demokritos.gr/publications/papers/2025/debs2025.pdf)) | 运行时自适应 / RTCEF separates engine, observer, collector, controller/optimiser, and model factory over Kafka. [Author code](https://github.com/manospits/rtcef), [v1.0.0 archive DOI](https://doi.org/10.5281/zenodo.15229227). |
| 2026 | Ntouni, Banelas, Alevizos, Giatrakos, [Optimized Edge-to-Cloud Complex Event Recognition and Forecasting on Altair AI Studio](https://cer.iit.demokritos.gr/publications/papers/2026/mdm2026.pdf) | 边缘到云集成 / An Altair AI Studio integration of forecasting and deployment placement. Registered as a later systems extension; a local Wayeb/RTCEF check does not validate the Altair platform integration. |

## Scope and interpretation

The user's local 2017 PDF was checked for title, authors and DOI. The author checkout additionally supplies papers under `upstream/Wayeb/docs/papers/`; these are convenient reading copies from the authors' repository.

The forecast horizon is measured in **future event steps（未来事件步数）**. It is not automatically elapsed wall-clock time. Synthetic validation can establish a working installation and narrowly check algorithmic behaviour; it cannot establish the published real-data accuracy, throughput, concept-drift performance or a scientific superiority claim.

