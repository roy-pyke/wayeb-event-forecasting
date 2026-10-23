"""Restore only checksum-verified source models; refuse to overwrite different files."""
import argparse
import hashlib
import io
import json
from pathlib import Path
import tarfile
import urllib.request
from queryforecast.common import CACHE,REPORTS

parser=argparse.ArgumentParser();parser.add_argument('--destination',type=Path,default=CACHE)
args=parser.parse_args()
manifest=json.loads((REPORTS/'SOURCE_ARTIFACT.json').read_text())
blob=urllib.request.urlopen(manifest['url'],timeout=60).read()
if hashlib.sha256(blob).hexdigest()!=manifest['archive_sha256']:raise RuntimeError('archive checksum mismatch')
with tarfile.open(fileobj=io.BytesIO(blob),mode='r:gz') as archive:
    members=archive.getmembers()
    if {m.name for m in members}!=set(manifest['files']):raise RuntimeError('unexpected archive member')
    payloads={}
    for member in members:
        if not member.isfile() or Path(member.name).is_absolute() or '..' in Path(member.name).parts:
            raise RuntimeError('unsafe archive member')
        data=archive.extractfile(member).read()
        if hashlib.sha256(data).hexdigest()!=manifest['files'][member.name]:raise RuntimeError('model checksum mismatch')
        target=args.destination/member.name
        if target.exists() and hashlib.sha256(target.read_bytes()).hexdigest()!=manifest['files'][member.name]:
            raise RuntimeError(f'refusing to overwrite different model: {target}')
        payloads[target]=data
    for target,data in payloads.items():target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(data)
print(json.dumps({'restored':list(manifest['files']),'destination':str(args.destination.resolve()),'verified':True}))
