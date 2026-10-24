# 复现 / Reproducibility

本轮工作位于 `recurrent_research/`，与固定的Wayeb/RTCEF子模块和旧ACN实验独立。使用Python 3.12.14、NumPy1.26.4；其余直接依赖固定于 requirements.txt。原始数据只从公开提供方获取，不需要密钥。

从仓库根目录运行：

```bash
./recurrent_research/reproduce.sh
```

已有ACN环境时使用 `.tools/acn/venv/bin/python`。新机器可显式建环境：

```bash
python3.12 -m venv .tools/recurrent/venv
.tools/recurrent/venv/bin/python -m pip install -r recurrent_research/requirements.txt
RECURRENT_PYTHON=.tools/recurrent/venv/bin/python ./recurrent_research/reproduce.sh
```

脚本依次：校验归档/原始文件 → 只拟合主域训练段 → 语义测试 → 重跑开发选择 → 原留出测试 → 全上线负对照 → 冻结的R2B价格基线 → 机制审计 → 独立R2C → 图表与聚合校验。重复运行是在重现既定结果，不重置“开发/测试是否已看过”的研究历史。运行耗时随CPU/缓存变化；完成价值、动作、采样、置信区间由固定输入和种子决定。

## 输入与输出

- 原始文件及归档：`artifacts/recurrent/r2/`，忽略不上传。归档SHA-256 `043a7d81c0b98de1a093d7aa9fbe57527924eb4bb013d7d39cbd313683ce46e0`。
- 源文件逐一散列：`reports/r2/sources.json`、`sources_r2c.json`；获取脚本拒绝变化的输入。
- 四份冻结协议：`configs/PROTOCOL_R2.json`、`DIAGNOSTICS_R2.json`、`BASELINE_AUDIT_R2B.json`、`INDEPENDENT_R2C.json`。
- 模型与选择：`reports/r2/model.json`、`selection.json`；原始模型SHA-256 `86c041cd1d85c06fc10abd12708c86c17d6d139ea4017bcedfc6e2d84fc4afb5`。
- 每次回放的聚合统计：`dev_windows.csv`、`test_windows.csv`、`baseline_audit_windows.csv`、`independent_r2c_windows.csv`。不包含原始节点地址、请求或用户名。
- 汇总与诊断：同目录JSON；图表PNG/SVG/PDF可独立引用。`verification.json`包含环境、代码/协议散列、守恒检查与测试结果。

单独运行语义检查：

```bash
.tools/acn/venv/bin/python -m pytest -q recurrent_research/tests
.tools/acn/venv/bin/python recurrent_research/scripts/verify.py
```

## 不可混淆的语义

每个回放有6个目的地，共12条缓冲记录，每个时槽最多K个不同目的地的队首请求。失败不会删除请求，成功完成一条，过期和缓冲拒绝都计数。价值1/2/4没有货币单位。网站/PlanetLab/PC时槽分别600/900/3600秒，不把小时级数据加速成毫秒生产trace。状态在本模型中不受这些小负载干预，故重放只检验该明确假设下的条件性价值。

控制器初始共同获得上一采样时刻的状态；之后只看自己请求的响应。所有未来真实状态和未来请求到达由环境持有，控制接口不接收这些数组。当前状态oracle是显式例外；没有任何全未来oracle或从历史真实最终结果推测需求的回填。

数据下载工具和文献/源码阅读没有启动HTTP生产服务，也没有向他人发送消息。Flink仅做固定源码审计，未部署或修改其运行时；不能用本目录测试成功替代真实Flink集成测试。
