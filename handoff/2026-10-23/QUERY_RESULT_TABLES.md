# 已保存查询结果的交接审计

日期：2026-10-23。只读已有 NPZ/JSON，不做新训练/采样/计时。MSE是对同一冻结神经源精确参考的均方误差。
预算均为2048 model rows；秒数来自原并发实验，不能用于最终串行成本验收。不同起点数的行不可直接排名。

## air：原始保存范围

| 阶段/方法 | 起点 | MSE | 并发秒/查询 | 实际平均源行 | 秩失败 |
|---|---:|---:|---:|---:|---:|
| balanced/harmonic | 48/48 | 2.36014555e-06 | 0.459859 | 2048.000 | 0 |
| balanced/mass | 48/48 | 0.00061494253 | 0.158838 | 2048.000 | 0 |
| balanced/monitor_we | 48/48 | 1.07687403e-05 | 0.040370 | 2048.000 | 0 |
| balanced/mc | 48/48 | 9.15474401e-05 | 0.014816 | 768.901 | 0 |
| balanced/potential | 48/48 | 1.56024303e-05 | 0.073920 | 768.901 | 0 |
| balanced/potential_lhs | 48/48 | 8.33403359e-06 | 0.074741 | 775.686 | 0 |
| balanced/potential_family_projected | 48/48 | 1.51286385e-05 | 0.074357 | 768.901 | 0 |
| balanced/potential_lhs_family_projected | 48/48 | 8.02740406e-06 | 0.075182 | 775.686 | 0 |
| balanced/independent_monitor_pool | 48/48 | 5.12401346e-05 | 0.096337 | 1685.424 | 0 |
| balanced/surrogate_only | 48/48 | 0.00651491936 | 0.000397 | 1.000 | 0 |
| overflow/harmonic | 48/48 | 3.27025688e-06 | 0.127006 | 2048.000 | 0 |
| overflow/mass | 48/48 | 2.95874756e-05 | 0.069998 | 2048.000 | 0 |
| overflow/known_bits | 48/48 | 2.91008446e-06 | 0.099622 | 2048.000 | 0 |
| overflow/uniform | 48/48 | 3.03125432e-06 | 0.127558 | 2048.000 | 0 |
| moment-basis-v2/harmonic | 42/48 | 6.19695157e-06 | 0.143591 | 2048.000 | 0 |
| moment-basis-v2/uniform | 42/48 | 3.79700655e-06 | 0.144093 | 2048.000 | 0 |
| moment-basis-v2/known_bits | 42/48 | 0.000208473155 | 0.127288 | 2048.000 | 0 |
| moment-basis-v2/occupancy | 42/48 | 2.62406549e-07 | 0.199477 | 2048.000 | 0 |
| moment-basis-v2/occupancy_symbol | 42/48 | 1.46564333e-07 | 0.434364 | 2048.000 | 0 |
| finite-closure/finite_occupancy | 19/48 | 2.20326305e-07 | 0.306857 | 2048.000 | 0 |
| markov-control/balanced | 48/48 | 1.30598856e-06 | 0.140406 | 2048.000 | 0 |
| markov-control/cv | 48/48 | 1.27643586e-06 | 0.072404 | 794.634 | 0 |
| markov-control/lhs | 48/48 | 9.2218005e-07 | 0.073108 | 800.492 | 0 |
| markov-control/cv_family_projected | 48/48 | 1.27621168e-06 | 0.072228 | 794.634 | 0 |
| markov-control/lhs_family_projected | 48/48 | 9.21548081e-07 | 0.073051 | 800.492 | 0 |
| particle-control/systematic | 48/48 | 1.40570889e-05 | 0.021617 | 1677.589 | 0 |
| particle-control/stratified | 48/48 | 1.91758271e-05 | 0.021205 | 1648.024 | 0 |
| particle-control/discrete | 48/48 | 1.02973162e-05 | 0.022073 | 2048.000 | 0 |
| particle-control/discrete_ordered | 48/48 | 5.27576232e-06 | 0.055888 | 2048.000 | 0 |

### air：只取全部阶段共有的 19 个起点

下面仍是不完整的前缀诊断，不能作为完整开发/非劣性/独立确认。未计算新的置信区间。

| 方法 | 相同起点 MSE |
|---|---:|
| moment-basis-v2/harmonic | 5.49282652e-06 |
| moment-basis-v2/uniform | 4.36465096e-06 |
| moment-basis-v2/known_bits | 0.000255417464 |
| moment-basis-v2/occupancy | 3.68637464e-07 |
| moment-basis-v2/occupancy_symbol | 2.14685902e-07 |
| finite-closure/finite_occupancy | 2.20326305e-07 |
| markov-control/balanced | 1.81135554e-06 |
| markov-control/cv | 1.64791718e-06 |
| markov-control/lhs | 1.29747803e-06 |
| markov-control/cv_family_projected | 1.6475916e-06 |
| markov-control/lhs_family_projected | 1.2959803e-06 |

共有起点精确参考向量最大差：0。

## power：原始保存范围

| 阶段/方法 | 起点 | MSE | 并发秒/查询 | 实际平均源行 | 秩失败 |
|---|---:|---:|---:|---:|---:|
| balanced/harmonic | 48/48 | 1.85486949e-06 | 0.449819 | 2048.000 | 0 |
| balanced/mass | 48/48 | 0.0019236749 | 0.155511 | 2048.000 | 0 |
| balanced/monitor_we | 48/48 | 9.68427286e-05 | 0.038930 | 2048.000 | 0 |
| balanced/mc | 48/48 | 0.000130355738 | 0.019553 | 1240.889 | 0 |
| balanced/potential | 48/48 | 6.19111435e-06 | 0.114905 | 1240.889 | 0 |
| balanced/potential_lhs | 48/48 | 3.95642897e-06 | 0.115512 | 1246.644 | 0 |
| balanced/potential_family_projected | 48/48 | 6.19098053e-06 | 0.115045 | 1240.889 | 0 |
| balanced/potential_lhs_family_projected | 48/48 | 3.95636385e-06 | 0.115587 | 1246.644 | 0 |
| balanced/independent_monitor_pool | 48/48 | 0.000126006375 | 0.104160 | 1630.954 | 0 |
| balanced/surrogate_only | 48/48 | 0.000995452773 | 0.000395 | 1.000 | 0 |
| overflow/harmonic | 48/48 | 2.62660605e-06 | 0.121512 | 2048.000 | 0 |
| overflow/mass | 48/48 | 0.00014319216 | 0.067304 | 2048.000 | 0 |
| overflow/known_bits | 48/48 | 4.1616164e-06 | 0.095578 | 2048.000 | 0 |
| overflow/uniform | 48/48 | 2.71003606e-06 | 0.121166 | 2048.000 | 0 |
| moment-basis-v2/harmonic | 42/48 | 4.58569107e-06 | 0.141770 | 2048.000 | 0 |
| moment-basis-v2/uniform | 42/48 | 7.66370232e-06 | 0.142299 | 2048.000 | 0 |
| moment-basis-v2/known_bits | 42/48 | 0.000385027895 | 0.127343 | 2048.000 | 0 |
| moment-basis-v2/occupancy | 42/48 | 9.72431748e-07 | 0.197291 | 2048.000 | 0 |
| moment-basis-v2/occupancy_symbol | 42/48 | 4.31153487e-07 | 0.436725 | 2048.000 | 0 |
| finite-closure/finite_occupancy | 19/48 | 6.26839577e-07 | 0.305085 | 2048.000 | 0 |
| markov-control/balanced | 48/48 | 2.60588751e-06 | 0.139942 | 2048.000 | 0 |
| markov-control/cv | 48/48 | 2.46795162e-06 | 0.112538 | 1258.667 | 0 |
| markov-control/lhs | 48/48 | 1.68618489e-06 | 0.113112 | 1264.660 | 0 |
| markov-control/cv_family_projected | 48/48 | 2.46788464e-06 | 0.112358 | 1258.667 | 0 |
| markov-control/lhs_family_projected | 48/48 | 1.68609555e-06 | 0.112870 | 1264.660 | 0 |
| particle-control/systematic | 48/48 | 2.87493573e-05 | 0.023628 | 1908.352 | 0 |
| particle-control/stratified | 48/48 | 3.91603862e-05 | 0.022776 | 1848.136 | 0 |
| particle-control/discrete | 48/48 | 2.6863289e-05 | 0.022568 | 2048.000 | 0 |
| particle-control/discrete_ordered | 48/48 | 1.49789993e-05 | 0.056893 | 2048.000 | 0 |

### power：只取全部阶段共有的 19 个起点

下面仍是不完整的前缀诊断，不能作为完整开发/非劣性/独立确认。未计算新的置信区间。

| 方法 | 相同起点 MSE |
|---|---:|
| moment-basis-v2/harmonic | 5.82538667e-06 |
| moment-basis-v2/uniform | 7.64420596e-06 |
| moment-basis-v2/known_bits | 0.00042305965 |
| moment-basis-v2/occupancy | 1.1847333e-06 |
| moment-basis-v2/occupancy_symbol | 5.53656206e-07 |
| finite-closure/finite_occupancy | 6.26839577e-07 |
| markov-control/balanced | 3.24190448e-06 |
| markov-control/cv | 2.60335681e-06 |
| markov-control/lhs | 1.85449072e-06 |
| markov-control/cv_family_projected | 2.60318775e-06 |
| markov-control/lhs_family_projected | 1.85426519e-06 |

共有起点精确参考向量最大差：0。

## 状态修正

旧 `query_forecasting/reports/evidence-summary.json` 生成时 Markov 尚未完成，因此标注缺失；现有原始报告已完整，本表补充它。
Q5/Q6 完整报告不存在，不能以汇总缺失为零误差，也不能将某个先完成起点的好结果替代48起点计划。
Q5/Q6 两领域各42/19个已保存起点都可读；本次没有恢复剩余运行。源码哈希、逐NPZ哈希及报告重算差异见 AUDIT.json。
