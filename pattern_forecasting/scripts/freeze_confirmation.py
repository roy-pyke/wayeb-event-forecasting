"""Freeze a diagnostic replication after development; does not read holdouts."""
import argparse,json,subprocess
from patternforecast.common import ROOT,PACKAGE,CONFIG,CACHE,RUNS,REPORTS,FAMILY,write_json,sha256,protocol

p=argparse.ArgumentParser();p.add_argument('--replicate-seeds',action='store_true');a=p.parse_args()
if (CONFIG/'FROZEN.json').exists():raise RuntimeError('Freeze already exists; never overwrite silently')
subprocess.run(['git','diff','--quiet','HEAD'],cwd=ROOT,check=True)
commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
sources={str(path.relative_to(ROOT)):sha256(path) for folder in ['src','scripts','configs','scala']
         for path in sorted((PACKAGE/folder).rglob('*'))
         if path.is_file() and path.suffix in ['.py','.json','.sre','.txt','.scala'] and path.name!='FROZEN.json'}
entry=dict(date='2026-10-22',code_commit=commit,family=FAMILY,source_sha256=sources,
    purpose='Independent diagnostic replication after failed development superiority gates. Do not reinterpret an unexpected positive holdout as a rescued confirmatory superiority claim.',
    primary='Multisignal short-horizon coordinate codec versus the development-selected strongest identical-precision representation at epsilon=0.002.',
    interpretation='Check reproducibility, correctness, future-year and unseen-entity generalization; preserve all failed gates. New superiority hypotheses require new data.',
    uncertainty='Paired Monday-aligned recorded-clock weekly bootstrap, 1000 resamples, common weather weeks across stations; seed spread separately.',
    transport='Instantaneous reliable auxiliary delivery at each scored query, full business stream, agreed version and state. Application payload bytes only.',
    reserves='Air 2017 and power 2010 remain excluded from this replication.',datasets={})
for name in ['air','power']:
    report=json.loads((REPORTS/f'models-{name}-short.json').read_text())
    selected=report['selection'];models={}
    for family in ['hgb','extra_trees','gru','business','no_state']:
        best=selected[family]
        seeds=[20261022,20261023,20261024] if a.replicate_seeds and family in ['hgb','extra_trees','gru'] else [20261022]
        for seed in seeds:
            key=best['key'].replace('s20261022',f's{seed}')
            model=report['runs'][key]
            assert sha256(RUNS/name/f'{key}.joblib')==model['model_sha256']
            models[key]=model
    keys=[selected[f]['key'] for f in ['hgb','extra_trees','gru']]
    backbone=min(keys,key=lambda key:models[key]['brier_complete'])
    codec=REPORTS/f'codec-{name}-development-{backbone}-e0.002-n0.json'
    control='all'
    if codec.exists():
        policies=json.loads(codec.read_text())['policies']
        control=min([r for r in ['all','static','zero'] if r in policies],key=lambda r:policies[r]['bytes_per_query'])
    entry['datasets'][name]=dict(backbone=backbone,codec_comparator=control,models=models,
        cuts_sha256=sha256(CACHE/name/'cuts.json'),development_manifest_sha256=sha256(CACHE/name/'manifest-development.json'),
        confirmation=protocol()['datasets'][name]['confirmation'],report_sha256=sha256(REPORTS/f'models-{name}-short.json'))
write_json(CONFIG/'FROZEN.json',entry)
print('FROZEN',FAMILY,commit,flush=True)
