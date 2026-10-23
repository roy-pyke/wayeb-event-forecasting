"""Install isolated dependencies and pinned authors' code, then apply one patch.

Run with Python 3.12. Source clones remain pristine; pip installs a local wheel
whose preprocessing lookup is patched, keeping a checksum record.
"""
from pathlib import Path
import hashlib
import json
import subprocess
import sys
import venv

ROOT = Path(__file__).resolve().parents[2]
HERE = ROOT / 'acn_research'
TOOLS = ROOT / '.tools/acn'


def run(args, **kwargs):
    subprocess.run([str(x) for x in args], check=True, **kwargs)


def main():
    TOOLS.mkdir(parents=True, exist_ok=True)
    sources = json.loads((HERE / 'configs/SOURCES.json').read_text())
    for name in ['acnportal', 'adacharge']:
        source = sources[name]
        dest = TOOLS / name
        if not dest.exists():
            run(['git', 'clone', '--quiet', '--no-checkout', source['repository'], dest])
        if subprocess.check_output(['git', 'status', '--porcelain'], cwd=dest):
            raise RuntimeError(f'Refusing to reset changed source {dest}')
        run(['git', 'checkout', '--quiet', '--detach', source['commit']], cwd=dest)
    env = TOOLS / 'venv'
    if not (env / 'bin/python').exists():
        venv.EnvBuilder(with_pip=True).create(env)
    py = env / 'bin/python'
    lock = HERE / 'requirements-lock.txt'
    run([py, '-m', 'pip', 'install', '-r', lock if lock.exists() else HERE / 'requirements.txt'])
    run([py, '-m', 'pip', 'install', '--no-deps', '--force-reinstall', TOOLS / 'acnportal', TOOLS / 'adacharge'])
    code = r'''
from pathlib import Path
import acnportal, hashlib, json, platform, sys
p = Path(acnportal.__file__).parent / 'algorithms/preprocessing.py'
old = 'upper_bounds.get(session.station_id, float("inf"))'
new = 'upper_bounds.get(session.session_id, float("inf"))'
s = p.read_text()
assert s.count(old) == 1
original = hashlib.sha256(s.encode()).hexdigest()
p.write_text(s.replace(old, new))
import cvxpy, numpy, pandas
record = {'python': platform.python_version(), 'numpy': numpy.__version__, 'pandas': pandas.__version__, 'cvxpy': cvxpy.__version__, 'solvers': cvxpy.installed_solvers(), 'patch': {'from': old, 'to': new, 'original_sha256': original, 'patched_sha256': hashlib.sha256(p.read_bytes()).hexdigest()}}
Path(sys.argv[1]).write_text(json.dumps(record, indent=2) + '\n')
'''
    run([py, '-c', code, HERE / 'reports/environment.json'])
    with (HERE / 'requirements-lock.txt').open('w') as f:
        subprocess.run([str(py), '-m', 'pip', 'freeze', '--exclude', 'acnportal', '--exclude', 'adacharge'], stdout=f, check=True)
    print(f'Ready: {py}')


if __name__ == '__main__':
    main()
