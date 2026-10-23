"""Fetch every file in a pinned office tree, with Git-blob verification."""
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
import json
from urllib.parse import quote
import requests
from fetch_data import fetch, ROOT, HERE

TREE = '851d1158df75988922ab20f45b6b283c96d2645b'
COMMIT = 'abb7cf15cc7108913e965d4375cc7270d532b65f'


def main():
    dest = ROOT/'artifacts/acn/office'
    dest.mkdir(parents=True, exist_ok=True)
    listing = dest/'full_tree.json'
    if not listing.exists():
        r = requests.get(f'https://api.github.com/repos/tongxin-li/ACN-Data-Static/git/trees/{TREE}', timeout=60)
        r.raise_for_status(); listing.write_text(json.dumps(r.json()))
    tree = json.loads(listing.read_text())
    assert tree['sha'] == TREE and not tree['truncated']
    entries = [x for x in tree['tree'] if x['path'].endswith('.csv.gz')]
    assert len(entries) == 1474
    def one(e):
        url = f'https://raw.githubusercontent.com/tongxin-li/ACN-Data-Static/{COMMIT}/'+quote('time series data/office_01/Parking_Lot_01/'+e['path'], safe='/')
        return fetch(url, dest/'raw'/e['path'], e['sha'])
    rows = []
    with ThreadPoolExecutor(max_workers=4) as pool:
        for f in as_completed([pool.submit(one,e) for e in entries]):
            rows.append(f.result())
            if len(rows)%100 == 0: print('downloaded',len(rows),flush=True)
    rows.sort(key=lambda x:x['path'])
    manifest = dest/'full_download_manifest.json'
    manifest.write_text(json.dumps(rows,indent=2)+'\n')
    out={'tree_sha':TREE,'commit':COMMIT,'files':len(rows),'bytes':sum(x['bytes'] for x in rows),
         'manifest_sha256':hashlib.sha256(manifest.read_bytes()).hexdigest(),
         'scope':'Complete pinned static office tree, not all live ACN sessions'}
    (HERE/'reports/full_office_sources.json').write_text(json.dumps(out,indent=2)+'\n')
    print(json.dumps(out),flush=True)


if __name__=='__main__': main()
