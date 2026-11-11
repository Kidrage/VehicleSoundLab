"""Publish the verified shared-gain residual comparisons."""
import argparse
import json
from pathlib import Path
import sys
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--workspace',type=Path,required=True)
args=parser.parse_args()
sys.path.insert(0,str(args.workspace/'tools/python_deps'))
from residual_osc_v1.review import write
from drive_evidence_v1.sources import sha
root=args.workspace/'references/analysis/residual_osc_v1'
r=json.loads((root/'controls/verification.json').read_text(encoding='utf-8'))
assert r['result']=='pass' and r['build_sha256']==sha(root/'fitted/report.json')
result=write(args.workspace,root/'fitted',root/'review')
print(json.dumps(dict(page=result['page'],players=len(result['records'])),ensure_ascii=False))
