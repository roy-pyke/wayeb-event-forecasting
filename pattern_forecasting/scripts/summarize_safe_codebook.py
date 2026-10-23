"""Audit the registered gate without selecting a favorable random seed."""
import json
import numpy as np
from patternforecast.common import PACKAGE, write_json

folder = PACKAGE/'reports/multisignal'
protocol = json.loads((PACKAGE/'configs/SAFE_CODEBOOK.json').read_text())


def aggregate(entries):
    first = entries[0]
    for e in entries:
        assert e['weeks'] == first['weeks']
        assert e['week_query_counts'] == first['week_query_counts']
        assert e['week_scored_counts'] == first['week_scored_counts']
    result = {k:np.mean([e[k] for e in entries], axis=0) for k in [
        'bytes_per_query','bytes_per_query_with_setup','brier','excess_brier',
        'codeword_packets','fallback_packets','phases','week_byte_sums','week_excess_sums']}
    result.update({k:first[k] for k in ['weeks','week_query_counts','week_scored_counts','setup_bytes','queries']})
    result['seed_count'] = len(entries)
    result['seed_byte_range'] = [min(e['bytes_per_query'] for e in entries),max(e['bytes_per_query'] for e in entries)]
    result['violations'] = sum(e['bound_violations']+e['epsilon_violations'] for e in entries)
    return result


def paired(p, b):
    assert p['weeks'] == b['weeks']
    assert np.array_equal(p['week_scored_counts'], b['week_scored_counts'])
    rng = np.random.default_rng(20261022)
    ix = rng.integers(len(p['weeks']), size=(1000, len(p['weeks'])))
    pb, bb = [np.array(e['week_byte_sums']) for e in [p,b]]
    pe, be = [np.array(e['week_excess_sums']) for e in [p,b]]
    n = np.array(p['week_scored_counts'])
    savings = 1-pb[ix].sum(1)/bb[ix].sum(1)
    delta = (pe-be)[ix].sum(1)/n[ix].sum(1)
    return dict(relative_bytes_saved=1-pb.sum()/bb.sum(),
        byte_saving_ci=np.quantile(savings,[.025,.975]),
        brier_difference=float(p['brier']-b['brier']),
        brier_difference_ci=np.quantile(delta,[.025,.975]))


summary = dict(protocol='configs/SAFE_CODEBOOK.json', datasets={},
    uncertainty='Paired calendar-week bootstrap, averaged policy seeds before resampling; seed ranges separately reported. Pointwise, not simultaneous, intervals. Gate is development evidence, not a held-out success claim.')
for dataset in ['air','power']:
    r = json.loads((folder/f'safe-codebook-{dataset}-development.json').read_text())
    aggregates = {}
    for name in ['phase_uniform']+protocol['same_codebook_baselines']:
        entries = [v for k,v in r['policies'].items() if k.startswith(name+'-s')]
        expected = 5 if name in ['phase_uniform','uniform_current'] else 1
        assert len(entries) == expected, 'incomplete experiment'
        aggregates[name] = aggregate(entries)
    candidate = aggregates['phase_uniform']
    best = min(protocol['same_codebook_baselines'], key=lambda k:aggregates[k]['bytes_per_query'])
    references = json.loads((folder/f"codec-{dataset}-development-{r['backbone']}-e0.002-n0.json").read_text())
    comparisons = {k:paired(candidate, v) for k,v in aggregates.items() if k!='phase_uniform'}
    for mode in ['all','basis']:
        comparisons[f'coordinate_{mode}'] = paired(candidate, references['policies'][mode])
    targets = [comparisons[best], comparisons['coordinate_all']]
    gate = all(v['relative_bytes_saved']>=.05 and v['byte_saving_ci'][0]>0 and v['brier_difference']<=.0001
               for v in targets) and candidate['violations']==0
    lower = r['offline_codeword_switches']
    details = dict(coverage=r['coverage'],safe_count_quantiles=r['safe_count_quantiles'],
        precompute_seconds=r['precompute_seconds'],offline_codeword_switches=lower,
        covered_runs=r['covered_runs'],policies=aggregates,comparisons=comparisons,
        best_same_codebook=best,gate_passed=gate,
        expected_codeword_switches_over_offline=candidate['codeword_packets']/max(lower,1),
        fallback_byte_fraction=(candidate['bytes_per_query']*candidate['queries']-28*candidate['codeword_packets'])/
                               (candidate['bytes_per_query']*candidate['queries']))
    summary['datasets'][dataset] = details
    print(dataset, 'coverage', r['coverage'], 'best baseline', best, 'gate',gate,
          'vs best',comparisons[best], 'vs coordinate_all', comparisons['coordinate_all'])
summary['gate_passed'] = all(d['gate_passed'] for d in summary['datasets'].values())
summary['reserve_decision'] = 'keep closed' if not summary['gate_passed'] else 'eligible for a new source/model/protocol freeze before reserve preparation'
write_json(PACKAGE/'reports/safe-codebook-comparisons.json',summary)

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
fig, axes = plt.subplots(1, 2, figsize=(11, 4.5))
names = ['nearest','minimum_certificate','uniform_current','recent_minimax_4','recent_minimax_16','phase_uniform']
for ax,dataset in zip(axes,['air','power']):
    d = summary['datasets'][dataset]
    for name in names:
        p = d['policies'][name]
        ax.scatter(p['excess_brier'],p['bytes_per_query'],s=55 if name=='phase_uniform' else 35,
                   color='#b14c3c' if name=='phase_uniform' else '#376b86')
        label = name.replace('minimum_certificate','min certificate').replace('recent_minimax_','recent ').replace('_',' ')
        ax.annotate(label,(p['excess_brier'],p['bytes_per_query']),xytext=(4,5),textcoords='offset points',fontsize=7)
    ax.set_title(f'{dataset}: registered codebook test')
    ax.set_xlabel('Observed mean Brier increase')
    ax.set_ylabel('Application bytes per query')
    ax.grid(alpha=.2)
    ax.margins(x=.3,y=.18)
    ax.ticklabel_format(axis='x',style='sci',scilimits=(0,0))
fig.suptitle('Same codebook, information, loss guarantee and fallback; 5 random seeds averaged')
fig.tight_layout()
for extension in ['png','pdf']:
    fig.savefig(PACKAGE/f'reports/figures/safe-codebook-frontier.{extension}',dpi=180)
plt.close(fig)
