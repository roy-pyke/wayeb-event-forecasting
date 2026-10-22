# 复现入口与实验隔离

工作目录为仓库根目录。Python 3.12；作者 Wayeb 的 Java/sbt 部署沿用仓库既有脚本。首次运行：

```bash
./setup.sh  # fresh clones: build the pinned author Wayeb jar first
./pattern_forecasting/setup.sh
./pattern_forecasting/run.sh -m pytest pattern_forecasting/tests -q
./pattern_forecasting/run.sh pattern_forecasting/scripts/prepare.py
./pattern_forecasting/run.sh pattern_forecasting/scripts/verify_wayeb.py
./pattern_forecasting/run.sh pattern_forecasting/scripts/audit_data.py
./pattern_forecasting/run.sh pattern_forecasting/scripts/train.py
```

三个模式族分别为 `nested`（默认）、`directional`、`multisignal`。后两族设置环境变量后使用相同代码、独立配置、数据缓存、模型与报告目录，禁止交叉加载模型。例如：

```bash
PATTERN_FAMILY=multisignal ./pattern_forecasting/setup.sh
PATTERN_FAMILY=multisignal ./pattern_forecasting/run.sh pattern_forecasting/scripts/prepare.py
PATTERN_FAMILY=multisignal ./pattern_forecasting/run.sh pattern_forecasting/scripts/train.py --profile short
PATTERN_FAMILY=multisignal ./pattern_forecasting/run.sh pattern_forecasting/scripts/refresh.py --dataset air --backbone short-hgb-31-180-s20261022 --epsilon 0.0005 0.002 --full-coherence --strategies whole sparse greedy_delta greedy_loss
```

`--profile short` 的窗口为各数据集的 1、2、3 个原生时间单位；查询频率不变。数据准备文件包含下一次匹配时间与观测覆盖，因而多个窗口共用同一因果特征和事件流，但它们不是独立数据实验。

确认集只有在相应配置目录存在 `FROZEN.json` 时才允许生成。该文件应记录最终代码、模型、数据源、超参数、主要比较与失败解释的冻结；当前开发迭代中尚未创建。不得把旧 2020 MetroPT 数据称为独立确认，也不得在看见确认结果后改主要声明。

原始 UCI 文件只保存于忽略的缓存目录，首次下载及每次复用都核对固定 SHA-256。大模型和中间预测保存在忽略的 `runs/`，仓库保存完整脚本、协议与可审核的数值报告。报告中的按周簇统计保留多站点共享天气的相关性；时间采用数据记录的钟表时间，未擅自推定原始时区。

Python 路径可通过 `WAYEB_PYTHON` 指定。所有主预测器使用同一 20,000 个训练查询及相同缓存年龄增强，共 40,000 个视图；树模型展开风险区间后的训练行数因此更多。Isotonic 校准只使用校准时期，超参数只使用开发时期。注意力 GRU 是公开结构的 PyTorch 任务适配，不是原作者 TensorFlow 实验的精确复现。

坐标编译与编码入口：

```bash
PATTERN_FAMILY=multisignal ./pattern_forecasting/run.sh pattern_forecasting/scripts/compile_codec.py
PATTERN_FAMILY=multisignal ./pattern_forecasting/run.sh pattern_forecasting/scripts/affine_codec.py --dataset air --backbone short-gru-32-0.01-s20261022 --representations all zero basis
./pattern_forecasting/run.sh pattern_forecasting/scripts/summarize.py
```

只有在完成开发和种子复验、提交当前源代码之后，才运行 `freeze_confirmation.py`。多通道族使用 `--replicate-seeds`，其余诊断族不加该参数。冻结记录源代码、训练模型、阈值及开发清单的 SHA；`prepare.py --confirmation`、`confirmation.py` 和确认编码实验都会核对冻结身份。生成 `FROZEN.json` 后先提交并 push，再运行确认准备和评分；不得覆盖已有冻结文件。

```bash
PATTERN_FAMILY=multisignal ./pattern_forecasting/run.sh pattern_forecasting/scripts/train.py --datasets air power --profile short --replicates
PATTERN_FAMILY=multisignal ./pattern_forecasting/run.sh pattern_forecasting/scripts/freeze_confirmation.py --replicate-seeds
# Commit and push the freeze before the following confirmation commands.
PATTERN_FAMILY=multisignal ./pattern_forecasting/run.sh pattern_forecasting/scripts/prepare.py --datasets air power --confirmation
PATTERN_FAMILY=multisignal ./pattern_forecasting/run.sh pattern_forecasting/scripts/confirmation.py
```

模型训练采用固定种子和确定性 CPU 算法；归档对象包含耗时元数据，因此重训文件的 SHA 不承诺逐字节相同。冻结 SHA 用于确认正在评估的确实是选定的那份模型，科学复现应比较预测与统计结果，同时记录运行时版本和硬件差异。GitHub CI 的三个模式族矩阵测试不下载研究数据；正式数据、训练和作者 CLI 核验须按这里的独立入口运行。

## 从发布快照复算确认结果

90 个已训练模型另附在 GitHub 的 `pattern-research-20261022` 研究快照中。`reports/MODEL_ARTIFACT.json` 保存整个归档及每个模型的 SHA。它是实验复现资产，不是宣称新方法已达到论文门槛的产品发布。

在干净 clone 中可仅设置 Python 环境、下载模型及公开数据，然后复算；这条路径不需要重新训练，也不需要为评分启动 Kafka。作者识别引擎的独立核验仍需上面的 Java 构建。

```bash
python3.12 -m venv .venv-pattern
.venv-pattern/bin/python -m pip install -r pattern_forecasting/configs/requirements.txt
./pattern_forecasting/run.sh pattern_forecasting/scripts/download_models.py
PATTERN_FAMILY=multisignal ./pattern_forecasting/run.sh pattern_forecasting/scripts/prepare.py --datasets air power
PATTERN_FAMILY=multisignal ./pattern_forecasting/run.sh pattern_forecasting/scripts/prepare.py --datasets air power --confirmation
PATTERN_FAMILY=multisignal ./pattern_forecasting/run.sh pattern_forecasting/scripts/confirmation.py
PATTERN_FAMILY=multisignal ./pattern_forecasting/run.sh pattern_forecasting/scripts/affine_codec.py --dataset air --split confirmation --backbone short-gru-32-0.01-s20261022 --representations all zero basis
PATTERN_FAMILY=multisignal ./pattern_forecasting/run.sh pattern_forecasting/scripts/affine_codec.py --dataset power --split confirmation --backbone short-gru-64-0.05-s20261022 --representations all zero basis
```

`check_reproducibility.py` 则在不覆盖冻结模型的前提下，从头重训一个神经模型并比较 2,000 个开发查询；本机实际复验得到零差异。不要删除或修改原冻结记录来让不同模型通过确认校验。新的训练研究应另开协议和输出目录，并与历史确认报告区分。
