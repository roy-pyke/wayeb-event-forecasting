# 作者基线闭环验证

本页保留 B1 阶段、数值重分配容差修正之前的集成记录。当前 setup 安装 C2 完整修正版，其再次验证结果在 `reports/c2/native_baseline.json`；后续数值缺陷及修正见 `C1_FAILURE_DIAGNOSIS.md`。

实际执行固定版本的 ACN-Sim、AdaCharge 和 CLARABEL；没有替代求解器的 stub。六个集成场景共 352 次非空调度，检查 pilot/actual 约束、6A 档位、能量守恒和请求上界，全部通过。六个语义测试通过。此处是集成验证，不是原论文实验复现。

## 两类修正

1. `apply_upper_bound_estimate` 使用 session ID 查询估计器输出，修复原 station/session 错配；安装副本的前后 SHA256 在 environment.json。
2. 仿真默认接口把真实 `EV.departure` 放入 `SessionInfo.departure`，而优化器以它计算剩余时长。新接口改用用户声明的离开时间；测试改变真实离站时间不改变控制器输入。声明过期时只滚动延长一个控制周期。这里只使用到达即披露请求的集成夹具；真实数据仍须经过 request_asof。

## 量化反馈失效及强基线

三车各请求 2 kWh，公共容量 36A，允许 pilot 为 {0,6,12,18,24,30}A，控制周期 1 分钟；第一辆在第 10–30 分钟外生暂停。新动作重新计算实际电流。

| 反馈方法 | 总交付 kWh | 恢复之后该车交付 kWh |
|---|---:|---:|
| 修正键、原 1A 恢复增量 | 4.4096 | 0 |
| 再加 6A 探测下限 | 5.0336 | 0.6240 |
| 再用 6A 恢复增量 | 5.9904 | 1.5808 |
| 无暂停对照 | 5.9904 | — |

原因：估计上限降到 1A 后被离散投影取整成零；只把上限提升到 6A，下一次升到 7A、实际仍为 6A，严格的 1A 上升阈值又可能让估计停住。采用与档位相符的 6A 探测及恢复增量是常规基线修正，不是预测机制。在此夹具中无需未来预测已经恢复到无暂停对照水平。剩余 0.0096 kWh 是离散投影尾部不足，未强行补足或隐藏。

连续 pilot 对照可交付约 6 kWh，单独列出，不能与离散动作结果混作公平比较。

## 工程失败

- setuptools 84.2.1 已不含老作者代码依赖的 pkg_resources，完整导入失败。固定为 80.9.0；保留弃用警告，不声称已现代化作者源码。
- 第一轮完整求解成功后，保存估计历史遇到 NumPy int64 JSON 序列化错误。显式转换时间和边界数值后重跑全部场景。
- 最初只加探测下限不足以修复恢复停滞；保留这个失败对照并加入量化一致的基线。

当前复现：用 Python 3.12 运行 `acn_research/scripts/setup.py`，然后用 `.tools/acn/venv/bin/python acn_research/scripts/validate_native.py`。当前汇总在 `reports/c2/native_baseline.json`，轨迹在忽略目录 `artifacts/acn/native/c2/`。B1 历史记录 `reports/native_baseline.json` 不覆盖。
