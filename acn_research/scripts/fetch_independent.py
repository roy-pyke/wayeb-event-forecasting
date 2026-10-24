"""Outcome-independent pinned samples from two previously unused ACN sites."""
from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
import json
from urllib.parse import quote
import requests
from fetch_data import ROOT, HERE, fetch


def main():
    protocol = json.loads((HERE/'configs/LEARNED_PROTOCOL_R1.json').read_text())
    out = {}
    for site, spec in protocol['external_sites'].items():
        dest = ROOT/'artifacts/acn'/site
        dest.mkdir(parents=True, exist_ok=True)
        listing = dest/'r1_tree.json'
        if not listing.exists():
            response = requests.get('https://api.github.com/repos/tongxin-li/ACN-Data-Static/git/trees/'+spec['tree'], timeout=(10,90))
            response.raise_for_status()
            listing.write_text(json.dumps(response.json()))
        tree = json.loads(listing.read_text())
        assert tree['sha'] == spec['tree'] and not tree['truncated']
        entries = [e for e in tree['tree'] if e['path'].endswith('.csv.gz')]
        entries.sort(key=lambda e: hashlib.sha256((site+'/'+e['path']).encode()).hexdigest())
        selected = entries[:1200]
        (dest/'r1_selection.json').write_text(json.dumps(selected, indent=2)+'\n')
        print(site, 'selected', len(selected), 'of', len(entries), flush=True)
        def one(e):
            url = 'https://raw.githubusercontent.com/tongxin-li/ACN-Data-Static/'+protocol['static_commit']+'/'+quote(spec['directory']+'/'+e['path'], safe='/')
            return fetch(url, dest/'raw'/e['path'], e['sha'])
        rows, errors = [], []
        with ThreadPoolExecutor(max_workers=4) as pool:
            tasks = {pool.submit(one,e): e for e in selected}
            for task in as_completed(tasks):
                try: rows.append(task.result())
                except Exception as exc: errors.append({'path':tasks[task]['path'], 'error':str(exc)})
                if (len(rows)+len(errors))%100 == 0:
                    print(site, 'processed',len(rows)+len(errors),'errors',len(errors),flush=True)
        rows.sort(key=lambda r:r['path'])
        manifest=dest/'r1_download_manifest.json'
        manifest.write_text(json.dumps(rows,indent=2)+'\n')
        (dest/'r1_download_errors.json').write_text(json.dumps(errors,indent=2)+'\n')
        out[site]={'tree':spec['tree'],'population_files':len(entries),'selected':len(selected),'downloaded':len(rows),
                   'failures':len(errors),'bytes':sum(r['bytes'] for r in rows),
                   'selection_sha256':hashlib.sha256((dest/'r1_selection.json').read_bytes()).hexdigest(),
                   'manifest_sha256':hashlib.sha256(manifest.read_bytes()).hexdigest()}
        (HERE/'reports/r1').mkdir(exist_ok=True)
        (HERE/'reports/r1/data_sources.json').write_text(json.dumps(out,indent=2)+'\n')
        print(out[site],flush=True)
    if any(x['failures'] for x in out.values()): raise RuntimeError('Downloads incomplete; no replacements made')


if __name__=='__main__': main()
