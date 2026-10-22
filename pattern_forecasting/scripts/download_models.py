"""Restore the published model snapshot, validating every archived file."""
import json,urllib.request,zipfile
from pathlib import PurePosixPath
from patternforecast.common import ROOT,PACKAGE,sha256

manifest=json.loads((PACKAGE/'reports/MODEL_ARTIFACT.json').read_text())
archive=ROOT/'.cache/pattern_forecasting'/manifest['filename'];archive.parent.mkdir(parents=True,exist_ok=True)
if not archive.exists() or sha256(archive)!=manifest['sha256']:
    temporary=archive.with_suffix('.download')
    urllib.request.urlretrieve(manifest['url'],temporary)
    if sha256(temporary)!=manifest['sha256']:raise RuntimeError('Model archive checksum mismatch')
    temporary.replace(archive)
with zipfile.ZipFile(archive) as z:
    if set(z.namelist())!=set(manifest['models']):raise RuntimeError('Unexpected model archive members')
    for member,digest in manifest['models'].items():
        rel=PurePosixPath(member)
        if rel.is_absolute() or '..' in rel.parts or rel.parts[:2]!=('runs','pattern-forecasting'):
            raise RuntimeError('Unsafe model archive member')
        target=ROOT/member
        if target.exists():
            if sha256(target)!=digest:raise RuntimeError(f'Different local model exists; preserve it before restoring {member}')
            continue
        target.parent.mkdir(parents=True,exist_ok=True)
        temporary=target.with_suffix('.download')
        with temporary.open('wb') as out,z.open(member) as source:
            import shutil
            shutil.copyfileobj(source,out)
        if sha256(temporary)!=digest:raise RuntimeError(f'Model checksum mismatch: {member}')
        temporary.replace(target)
print('Validated',len(manifest['models']),'published models')
