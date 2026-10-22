import argparse
from patternforecast.data import prepare
from patternforecast.common import REPORTS,CONFIG,FAMILY,PACKAGE,write_json

p=argparse.ArgumentParser()
p.add_argument('--datasets',nargs='+',default=['air','power','metro'])
p.add_argument('--confirmation',action='store_true')
p.add_argument('--force',action='store_true')
args=p.parse_args()
if args.confirmation:
    from patternforecast.freeze import verify_freeze
    for name in args.datasets:verify_freeze(name)
results={name:prepare(name,args.confirmation,args.force) for name in args.datasets}
write_json(REPORTS/('data-confirmation.json' if args.confirmation else 'data-development.json'),results)
