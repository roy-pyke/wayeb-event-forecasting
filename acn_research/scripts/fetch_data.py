"""Fetch pinned public recordings and request exports; save aggregates only in Git.

Raw exports are mirrors, not authenticated live API responses. Their exact Git
blob hashes are checked; they cannot establish unchanged original-server bytes.
"""
from pathlib import Path
import argparse
import concurrent.futures
import hashlib
import json
import os
import sys
import time
from urllib.parse import quote
import requests

ROOT = Path(__file__).resolve().parents[2]
HERE = ROOT / 'acn_research'
sys.path.insert(0, str(HERE / 'src'))
from acnresearch.requests import recording_filename, request_asof, timestamp

MIRROR_COMMIT = '3b1cb67d1b02f8fea0451c16fbcfaee34449ce46'
MIRRORS = {
    'office': ('Office 1.json', '05223d164caf486b0f5056b43778317699fc3139'),
    'caltech': ('Caltech.json', '869ba5fb4329906d3a49df8ca26e29370b1f17a2'),
    'jpl': ('JPL.json', 'd4c32795d5b271ba6cc612b866179f969b0ea57f'),
}


def fetch(url, path, blob=None):
    if path.exists():
        data = path.read_bytes()
    else:
        response = requests.get(url, timeout=(10, 60), headers={'User-Agent': 'Wayeb-ACN-research/1.0'})
        response.raise_for_status()
        data = response.content
    actual = hashlib.sha1(b'blob ' + str(len(data)).encode() + b'\0' + data).hexdigest()
    if blob is not None and actual != blob:
        raise ValueError(f'Git blob mismatch: {path.name}')
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return {'url': url, 'path': str(path.relative_to(ROOT)), 'bytes': len(data),
            'sha256': hashlib.sha256(data).hexdigest(), 'git_blob_sha': actual}


def audit_sessions(sessions, selected_names):
    from collections import Counter
    from datetime import timedelta
    summary = Counter(sessions=len(sessions))
    matched = []
    modified_delay = []
    dates = []
    for s in sessions:
        dates.append(timestamp(s['connectionTime']))
        if recording_filename(s['sessionID']) in selected_names:
            matched.append(s)
        inputs = s.get('userInputs') or []
        summary['with_inputs'] += bool(inputs)
        summary['multiple_input_versions'] += len(inputs) > 1
        conn = timestamp(s['connectionTime'])
        for minutes in [0, 1, 10, 60]:
            try:
                r = request_asof(s, conn + timedelta(minutes=minutes))
                summary[f'valid_request_asof_connection_plus_{minutes}m'] += r is not None
            except ValueError:
                summary['conflicting_request_times'] += 1
        for x in inputs:
            try:
                modified_delay.append((timestamp(x['modifiedAt']) - conn).total_seconds())
            except (KeyError, TypeError, ValueError):
                summary['input_versions_without_valid_modifiedAt'] += 1
    summary = dict(summary)
    summary['connection_range'] = [min(dates).isoformat(), max(dates).isoformat()] if dates else []
    summary['matched_selected_recordings'] = len(matched)
    summary['matched_with_inputs'] = sum(bool(s.get('userInputs')) for s in matched)
    summary['input_versions_after_connection'] = sum(x > 0 for x in modified_delay)
    summary['input_versions_before_connection'] = sum(x < 0 for x in modified_delay)
    summary['input_versions_after_10_minutes'] = sum(x > 600 for x in modified_delay)
    return summary, matched


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--sites', nargs='+', default=['office', 'caltech', 'jpl'], choices=list(MIRRORS))
    parser.add_argument('--skip-recordings', action='store_true')
    args = parser.parse_args()
    raw = ROOT / 'artifacts/acn'
    protocol = json.loads((HERE / 'reference/acn_probe/protocol.json').read_text())
    selected = {Path(x['path']).name for x in protocol['selection_manifest']}
    report = {'scope': 'Descriptive audit of pinned third-party ACN session exports; not live API or a forecasting confirmation.',
              'mirror_repository': 'https://github.com/yvenn-amara/ev-load-open-data',
              'mirror_commit': MIRROR_COMMIT, 'selected_office_recordings': len(selected), 'sources': [], 'sites': {}}
    for site in args.sites:
        name, blob = MIRRORS[site]
        url = 'https://raw.githubusercontent.com/yvenn-amara/ev-load-open-data/' + MIRROR_COMMIT + '/' + quote('1. Input Data/7. ACN Data/' + name, safe='/')
        path = raw / 'requests' / (site + '.json')
        report['sources'].append(fetch(url, path, blob))
        payload = json.loads(path.read_text())
        sessions = payload['_items'] if isinstance(payload, dict) else payload
        summary, matched = audit_sessions(sessions, selected)
        report['sites'][site] = summary
        if site == 'office':
            (raw / 'requests/office_selected.json').write_text(json.dumps(matched))
        print(site, json.dumps(summary), flush=True)
    if not args.skip_recordings:
        def one(entry):
            rel = 'time series data/office_01/' + entry['path']
            url = 'https://raw.githubusercontent.com/' + protocol['repo'] + '/' + protocol['commit'] + '/' + quote(rel, safe='/')
            return fetch(url, raw / 'office/raw' / Path(entry['path']).name, entry['sha'])
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
            recordings = list(pool.map(one, protocol['selection_manifest']))
        (raw / 'office/download_manifest.json').write_text(json.dumps(recordings, indent=2) + '\n')
        report['recordings_downloaded'] = len(recordings)
        report['recording_bytes'] = sum(r['bytes'] for r in recordings)
        report['recording_manifest_sha256'] = hashlib.sha256((raw / 'office/download_manifest.json').read_bytes()).hexdigest()
    report['limitations'] = ['user request is declared intent, not physical battery demand',
                            'modifiedAt is submission time, not verified controller reception',
                            'missing userInputs is never filled using final kWhDelivered or disconnectTime',
                            'live API timed out; mirror identity to server bytes not established']
    (HERE / 'reports/request_data_audit.json').write_text(json.dumps(report, indent=2) + '\n')


if __name__ == '__main__':
    main()
