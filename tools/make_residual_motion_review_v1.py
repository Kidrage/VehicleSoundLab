"""Publish the residual amplitude-motion diagnostic, without autoplay."""
import argparse
from pathlib import Path
import sys
import json

parser = argparse.ArgumentParser(description=__doc__)
for name in ('workspace', 'fit', 'verification', 'out'):
    parser.add_argument('--'+name, type=Path, required=True)
args = parser.parse_args()
sys.path.insert(0, str(args.workspace/'tools/python_deps'))
from residual_motion_v1.review import write

result = write(args.workspace, args.fit, args.verification, args.out)
print(json.dumps(dict(page=result['page'], players=len(result['records'])), ensure_ascii=False))
