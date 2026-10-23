"""Package already-saved research files and evidence; no experimental execution."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import zipfile

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
parser=argparse.ArgumentParser()
parser.add_argument('--output',type=Path,required=True)
args=parser.parse_args()
args.output.mkdir(parents=True,exist_ok=True)
audit=json.loads((HERE/'AUDIT.json').read_text())
files=json.loads((HERE/'FILE_MANIFEST.json').read_text())
members={}
def add(path,name,expected=None):
    data=path.read_bytes()
    digest=hashlib.sha256(data).hexdigest()
    if expected is not None and digest!=expected:raise ValueError(f'Changed artifact: {path}')
    if name in members:raise ValueError(f'Duplicate member: {name}')
    members[name]=(data,digest)
for f in files['files']:
    add(ROOT/f['path'],'repository/'+f['path'],f['sha256'])
for p in sorted(HERE.iterdir()):
    if p.is_file() and p.suffix in ('.md','.json','.py'):
        add(p,'repository/'+str(p.relative_to(ROOT)))
for domain,d in audit['domains'].items():
    for mode,m in d['modes'].items():
        base=ROOT/'.cache/query_forecasting'/domain/mode
        if json.loads((base/'identity.json').read_text())!=m['identity']:
            raise ValueError('Changed experiment identity')
        add(base/'identity.json',f'saved_query_evidence/{domain}/{mode}/identity.json')
        for name,digest in m['files'].items():
            add(base/name,f'saved_query_evidence/{domain}/{mode}/{name}',digest)

top='''# Wayeb research handoff — 2026-10-23

Start with `repository/handoff/2026-10-23/SEND_TO_GPT6_PRO.md`.
It contains the reviewer prompt, full Chinese dossier and saved result tables.

`repository/` contains all files tracked by the research snapshot, two subsequently completed Markov reports and this handoff.
`saved_query_evidence/` contains saved NPZ/identity evidence for six query stages: complete controls and incomplete Q5/Q6.
`PACK_MANIFEST.json` lists SHA256 of every other archive member.

No experiments were resumed to assemble this package. No untouched reserve cohort was evaluated.
This is an audit package, not an offline installation: upstream submodule sources, raw datasets, virtual environments and large model collections are excluded. Fixed upstream hashes and verified model-release restoration instructions are in the dossier.
'''.encode()
members['README.md']=(top,hashlib.sha256(top).hexdigest())
manifest={'research_head':audit['research_head'],
          'documentation_commit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
          'scope':'Existing artifacts only; no new experiment. File-level SHA256 excludes this manifest itself.',
          'files':[{'path':k,'bytes':len(v[0]),'sha256':v[1]} for k,v in sorted(members.items())]}
archive=args.output/'wayeb-gpt6-pro-handoff-2026-10-23.zip'
with zipfile.ZipFile(archive,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
    for name,(data,_) in sorted(members.items()):z.writestr(name,data)
    z.writestr('PACK_MANIFEST.json',json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
with zipfile.ZipFile(archive) as z:
    assert z.testzip() is None
    for row in manifest['files']:
        assert hashlib.sha256(z.read(row['path'])).hexdigest()==row['sha256']
for name in ['SEND_TO_GPT6_PRO.md','GPT6_PRO_PROMPT.md','APPLICATION_CONTEXT.md','APPLICATION_SOURCES.json','PROJECT_DOSSIER.zh-CN.md',
             'QUERY_CODE_CONTEXT.md','SOURCE_DOCUMENTS.md','README.md']:
    shutil.copyfile(HERE/name,args.output/name)
result={'archive':str(archive),'bytes':archive.stat().st_size,
        'sha256':hashlib.sha256(archive.read_bytes()).hexdigest(),
        'members_verified':len(manifest['files']),
        'crc_and_sha256_verification':'passed',
        'research_head':audit['research_head'],
        'documentation_commit':manifest['documentation_commit']}
(args.output/'PACKAGE_VERIFICATION.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result,indent=2))
