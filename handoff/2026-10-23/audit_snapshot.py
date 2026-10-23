"""Read existing artifacts only; never import or execute experiment runners."""
import hashlib
import json
from pathlib import Path
import subprocess
import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
Q = ROOT / 'query_forecasting'
CACHE = ROOT / '.cache/query_forecasting'

def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()

def git(*args, cwd=ROOT):
    return subprocess.check_output(['git', *args], cwd=cwd, text=True).strip()

out = {'date': '2026-10-23 America/Los_Angeles',
       'scope': 'Read-only handoff audit of existing artifacts; no new training, sampling, reserve access or timing.',
       'research_head': git('rev-parse', 'HEAD'),
       'status_at_start': git('status', '--short'),
       'submodules': {}, 'frozen_sources': [], 'domains': {}}
for name in ['Wayeb', 'rtcef']:
    p = ROOT / 'upstream' / name
    out['submodules'][name] = {'head': git('rev-parse', 'HEAD', cwd=p),
                                'status': git('status', '--short', cwd=p)}
for rel, key, base in [
    ('state_forecasting/configs/FROZEN.json', 'source_hashes', ROOT/'state_forecasting'),
    ('state_forecasting/configs/FROZEN_2022.json', 'hashes', ROOT/'state_forecasting'),
    *[(f'pattern_forecasting/configs/{family}FROZEN.json', 'source_sha256', ROOT)
      for family in ['', 'directional/', 'multisignal/']]]:
    d = json.loads((ROOT/rel).read_text())[key]
    bad = [p for p, h in d.items() if not (base/p).is_file() or sha(base/p) != h]
    out['frozen_sources'].append({'manifest': rel, 'checked': len(d), 'mismatches': bad})

methods = {
    'balanced': ['harmonic','mass','monitor_we','mc','potential','potential_lhs',
                 'potential_family_projected','potential_lhs_family_projected','independent_monitor_pool','surrogate_only'],
    'overflow': ['harmonic','mass','known_bits','uniform'],
    'moment-basis-v2': ['harmonic','uniform','known_bits','occupancy','occupancy_symbol'],
    'finite-closure': ['finite_occupancy'],
    'markov-control': ['balanced','cv','lhs','cv_family_projected','lhs_family_projected'],
    'particle-control': ['systematic','stratified','discrete','discrete_ordered']}
for domain in ['air', 'power']:
    domain_out = {'model_sha256': sha(CACHE/domain/'world.pt'), 'modes': {}}
    all_values = {}
    for mode, names in methods.items():
        folder = CACHE/domain/mode
        files = sorted(folder.glob('origin-*.npz'))
        records = {}
        for p in files:
            with np.load(p, allow_pickle=False) as z:
                records[int(p.stem.split('-')[-1])] = {k: z[k] for k in z.files}
        all_values[mode] = records
        d = {'completed_origins': len(files), 'planned_origins': 48,
             'origin_ids': sorted(records), 'file_bytes': sum(p.stat().st_size for p in files),
             'files': {p.name: sha(p) for p in files}, 'methods_at_2048': {},
             'status': 'complete existing run' if len(files)==48 else 'INCOMPLETE: descriptive prefix only; not a gate result'}
        ident = json.loads((folder/'identity.json').read_text())
        d['identity'] = ident
        d['current_source_mismatches'] = [p for p,h in ident.get('sources',{}).items()
                                         if not (Q/p).is_file() or sha(Q/p)!=h]
        d['model_matches'] = ident['model'] == domain_out['model_sha256']
        report = Q/'reports'/f'{domain}-{mode}.json'
        d['report_exists'] = report.exists()
        d['report_sha256'] = sha(report) if report.exists() else None
        original_report = json.loads(report.read_text()) if report.exists() else None
        for k,name in enumerate(names):
            estim = np.array([v['estimates'][1,k] for v in records.values()])
            truth = np.array([v['truth'] for v in records.values()])
            good = np.array([v.get('feasible',np.ones(v['rows'].shape,bool))[1,k] for v in records.values()])
            failures = int((~good).sum())
            mse = float(np.mean((estim-truth[:,None,:])**2)) if not failures else None
            stats = {'mse': mse, 'infeasible_runs': failures,
                     'seconds_concurrent':float(np.mean([v['seconds'][1,k] for v in records.values()])),
                     'mean_source_rows':float(np.mean([v['rows'][1,k] for v in records.values()])),
                     'replicates_per_origin':int(estim.shape[1]),
                     'estimate_shape':list(estim.shape)}
            if original_report:
                rr = next(r for r in original_report['results'] if r['budget']==2048 and r['method']==name)
                stats['report_mse_abs_difference'] = abs(mse-rr['mse']) if mse is not None else None
            if all('ranks' in v for v in records.values()):
                stats['max_rank'] = int(max(v['ranks'][1,k].max() for v in records.values()))
            d['methods_at_2048'][name] = stats
        domain_out['modes'][mode] = d
    # Compare only identical saved origins and exact reference vectors.
    shared = sorted(set.intersection(*(set(v) for v in all_values.values())))
    maxdiff = 0.
    for i in shared:
        ref = all_values['balanced'][i]['truth']
        for records in all_values.values():
            maxdiff=max(maxdiff,float(np.max(np.abs(ref-records[i]['truth']))))
    domain_out['common_origin_ids_all_modes'] = shared
    domain_out['max_reference_difference_common_origins'] = maxdiff
    domain_out['matched_partial_2048'] = {}
    for mode in ['moment-basis-v2','finite-closure','markov-control']:
        for k,name in enumerate(methods[mode]):
            v = [all_values[mode][i] for i in shared]
            mse = float(np.mean([np.mean((r['estimates'][1,k]-r['truth'])**2) for r in v]))
            domain_out['matched_partial_2048'][mode+'/'+name] = mse
    out['domains'][domain] = domain_out
(HERE/'AUDIT.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n')
for domain,d in out['domains'].items():
    print(domain)
    for mode,m in d['modes'].items():
        print(mode,m['completed_origins'],[(k,v['mse']) for k,v in m['methods_at_2048'].items()])
    print('matched partial:', d['matched_partial_2048'])
print('freeze:',out['frozen_sources'])
