"""Assemble readable source/index supplements from saved project files only."""
import ast
import hashlib
import json
from pathlib import Path
import subprocess

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
AUDIT=json.loads((HERE/'AUDIT.json').read_text())
HEAD=AUDIT['research_head']

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def git(*args,cwd=ROOT):return subprocess.check_output(['git',*args],cwd=cwd,text=True).strip()
def put(name,text):(HERE/name).write_text(text.rstrip()+'\n')

paths=[Path(p) for p in git('ls-tree','-r','--name-only',HEAD).splitlines() if (ROOT/p).is_file()]
paths += [Path(f'query_forecasting/reports/{d}-markov-control.json') for d in ['air','power']]
paths=sorted(set(paths))
manifest={'research_head':HEAD,'scope':'Original research tracked files plus two completed, previously uncommitted Markov reports. Handoff-generated files have a separate archive manifest.',
          'files':[{'path':str(p),'bytes':(ROOT/p).stat().st_size,'sha256':sha(ROOT/p)} for p in paths], 'upstream':{}}
inventory=['# 全文件结构与实现符号索引', '', f'研究代码基准 `{HEAD}`。列表包括本仓库全部文件与两个原样纳入的完成报告。', '',
           '## 本仓库文件（不含依赖/数据缓存）','', '```text']
inventory += [str(p) for p in paths]
inventory += ['```','','## Python 顶层符号（定位入口；并非运行证据）','']
for p in paths:
    if p.suffix!='.py':continue
    tree=ast.parse((ROOT/p).read_text())
    names=[f'{n.name} (L{n.lineno})' for n in tree.body if isinstance(n,(ast.ClassDef,ast.FunctionDef,ast.AsyncFunctionDef))]
    if names:inventory.append(f'- `{p}`：'+', '.join(names))
for name in ['Wayeb','rtcef']:
    base=ROOT/'upstream'/name
    files=git('ls-files',cwd=base).splitlines()
    manifest['upstream'][name]={'head':git('rev-parse','HEAD',cwd=base),'tracked_paths':files}
    inventory += ['',f'## 作者子模块 {name}：全部追踪路径','',
                  f'固定 SHA `{manifest["upstream"][name]["head"]}`。源码不复制进附件，请按 Git 子模块恢复并保留许可。','', '```text',*files,'```']
inventory += ['','## 本地忽略目录','',
              '`runs/` 是历史日志/训练/回放；`.cache/` 是数据、模型、逐起点估计；`.venv*/` 是依赖；`.tools/` 是构建工具。',
              '这些不是新科学结论。附件仅另外纳入明确列出的查询检查点证据，不含原始传感器大文件或任何储备结果。',
              '本次交接目录的所有文件另见 ZIP 的 PACK_MANIFEST.json；不将生成的归档再递归打入自己。']
put('FILE_INVENTORY.md','\n'.join(inventory))
put('FILE_MANIFEST.json',json.dumps(manifest,ensure_ascii=False,indent=2))

history=git('log',HEAD,'--reverse','--date=iso-strict','--format=%H | %aI | %s')
put('COMMIT_HISTORY.md','# 研究提交历史\n\n按提交图从早到晚列出至研究基准。作者时间采用Git保存时区，不以文件mtime判断先后。\n\n```text\n'+history+'\n```')

docs=[Path('README.md')]
docs += [p for p in paths if p.suffix=='.md' and (str(p).startswith('docs/') or '/docs/' in str(p) or (len(p.parts)==2 and p.name=='README.md'))]
docs=list(dict.fromkeys(docs))
source=['# 原研究文档逐字汇编','',
        '这是一份保留历史语境的原文附件。文中的“现在/继续/正在运行”属于当时阶段；当前所有实验暂停。',
        '此汇编没有改写原文，也不自动修复旧 evidence-summary 的缺失项；以主交接文档和 AUDIT.json 的状态核对为准。',
        '文献检索记录来自原阶段，本次整理未新作穷尽检索。所有路径相对于仓库根。','']
for p in docs:
    source += ['---','',f'# 原文件：`{p}`',f'SHA256: `{sha(ROOT/p)}`','',(ROOT/p).read_text(),'']
source += ['---','','# 结果前登记协议原文','']
protocols=[p for p in paths if p.suffix=='.json' and '/configs/' in str(p) and p.name not in ['dfa.json'] and not p.name.startswith('FROZEN')]
for p in protocols:
    source += [f'## `{p}`','','```json',(ROOT/p).read_text().rstrip(),'```','']
put('SOURCE_DOCUMENTS.md','\n'.join(source))

code=[
 'query_forecasting/src/queryforecast/model.py','query_forecasting/src/queryforecast/data.py',
 'query_forecasting/compositional/monitor.py','query_forecasting/compositional/propagation.py',
 'query_forecasting/occupancy/features.py','query_forecasting/occupancy/recombine.py',
 'query_forecasting/occupancy/propagate.py','query_forecasting/engineering/constants.py',
 'query_forecasting/finite_control/finite_features.py','query_forecasting/finite_control/finite_method.py',
 'query_forecasting/markov_control/potential.py','query_forecasting/markov_control/methods.py',
 'query_forecasting/particle_controls/resample.py','query_forecasting/particle_controls/method.py',
 'query_forecasting/tests/test_occupancy.py','query_forecasting/tests/test_finite_control.py',
 'query_forecasting/scripts/moment_basis_experiment.py','query_forecasting/scripts/finite_closure_experiment.py',
 'query_forecasting/scripts/markov_control_experiment.py','query_forecasting/scripts/summarize_evidence.py']
ct=['# 当前候选与强对照的完整代码摘录','',
    '按文件逐字拼接，供不能解压附件时审阅。完整项目的其余代码/测试在 ZIP。未执行任何实验。','']
for p in code:
    ct += [f'## `{p}`',f'SHA256 `{sha(ROOT/p)}`','','```python',(ROOT/p).read_text().rstrip(),'```','']
put('QUERY_CODE_CONTEXT.md','\n'.join(ct))

tables=['# 已保存查询结果的交接审计','',
        '日期：2026-10-23。只读已有 NPZ/JSON，不做新训练/采样/计时。MSE是对同一冻结神经源精确参考的均方误差。',
        '预算均为2048 model rows；秒数来自原并发实验，不能用于最终串行成本验收。不同起点数的行不可直接排名。','']
for dom,dd in AUDIT['domains'].items():
    tables += [f'## {dom}：原始保存范围','', '| 阶段/方法 | 起点 | MSE | 并发秒/查询 | 实际平均源行 | 秩失败 |', '|---|---:|---:|---:|---:|---:|']
    for mode,d in dd['modes'].items():
        for name,v in d['methods_at_2048'].items():
            mse='不可行' if v['mse'] is None else f"{v['mse']:.9g}"
            tables.append(f"| {mode}/{name} | {d['completed_origins']}/48 | {mse} | {v['seconds_concurrent']:.6f} | {v['mean_source_rows']:.3f} | {v['infeasible_runs']} |")
    tables += ['',f'### {dom}：只取全部阶段共有的 {len(dd["common_origin_ids_all_modes"])} 个起点','',
               '下面仍是不完整的前缀诊断，不能作为完整开发/非劣性/独立确认。未计算新的置信区间。','',
               '| 方法 | 相同起点 MSE |','|---|---:|']
    for name,mse in dd['matched_partial_2048'].items():tables.append(f'| {name} | {mse:.9g} |')
    tables += ['',f'共有起点精确参考向量最大差：{dd["max_reference_difference_common_origins"]:.3g}。','']
tables += ['## 状态修正','',
           '旧 `query_forecasting/reports/evidence-summary.json` 生成时 Markov 尚未完成，因此标注缺失；现有原始报告已完整，本表补充它。',
           'Q5/Q6 完整报告不存在，不能以汇总缺失为零误差，也不能将某个先完成起点的好结果替代48起点计划。',
           'Q5/Q6 两领域各42/19个已保存起点都可读；本次没有恢复剩余运行。源码哈希、逐NPZ哈希及报告重算差异见 AUDIT.json。']
put('QUERY_RESULT_TABLES.md','\n'.join(tables))

put('SEND_TO_GPT6_PRO.md',(HERE/'GPT6_PRO_PROMPT.md').read_text()+'\n\n---\n\n'+(HERE/'APPLICATION_CONTEXT.md').read_text()+'\n\n---\n\n'+(HERE/'PROJECT_DOSSIER.zh-CN.md').read_text()+'\n\n---\n\n'+(HERE/'QUERY_RESULT_TABLES.md').read_text())
put('README.md','''# 给 GPT‑6 Pro 的 Wayeb 研究交接包

先上传 `SEND_TO_GPT6_PRO.md`，其中已包含以用户口吻写的背景与想法、用户要求、完整主交接说明和当前结果表。
如支持 ZIP，再上传 `wayeb-gpt6-pro-handoff-2026-10-23.zip`，供核查全部代码、协议、原始报告与保存的查询检查点。

本次 prompt 修订撤下了指定检索步骤、候选数量、工作顺序和输出模板。它陈述经历、错误、问题与用户希望贴近真实开源工业应用的想法，由 GPT Pro 自主研究和判断。交接正文中原有的下一步建议保留为历史记录。

若只能附加少数文本文件，顺序是：

1. `SEND_TO_GPT6_PRO.md`：用户想法、要求与完整研究经历。
2. `QUERY_CODE_CONTEXT.md`：Q5/Q6、当前强基线和关键测试的逐文件完整代码。
3. `SOURCE_DOCUMENTS.md`：全部原设计/日志/结果/文献/复现文档及登记协议。
4. `AUDIT.json`、`FILE_INVENTORY.md`：核对结果身份和完整项目结构。

`APPLICATION_CONTEXT.md` 现在只保留用户的要求，原先的具体工业案例介绍已从合并文档移除。`APPLICATION_SOURCES.json` 是之前联网核查的历史来源记录，不作为 prompt 中预设的应用方向。

ZIP 根下 `repository/` 保持源码相对路径；`saved_query_evidence/` 是6类已保存查询实验的NPZ/identity（含完整基线与不完整Q5/Q6）。`PACK_MANIFEST.json` 给逐文件SHA256。
研究代码基准为 `96751ca`；两份后来完成的Markov报告随本次文档阶段原样归档。包中没有大原始数据、虚拟环境、Git凭据或作者子模块源码。作者代码与模型恢复地址写在主文档；这不是一个包含所有依赖的离线可运行镜像。

实验当前暂停。本次整理材料、核验已有结果并查阅公开来源，未恢复训练/采样、未进行新的性能测试、未打开储备年份。Q5各42/48起点，Q6各19/48；不能当作论文确认成功。

文档中的过程是可审计的设计依据、假设、修改和失败记录；不把未实施设想或预检当成完成成果。旧原文保留原时点的现在时，本README和主交接说明记录当前状态。
''')
print('Research files',len(paths),'source docs',len(docs),'protocols',len(protocols),'code files',len(code))
for p in sorted(HERE.glob('*.md')):print(p.name,p.stat().st_size)
