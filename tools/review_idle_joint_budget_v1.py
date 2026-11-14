"""Export the source-budget candidate through the shared finite review exporter."""
import argparse,sys
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__)
for key in ['workspace','input','audit','out']:p.add_argument('--'+key,type=Path,required=True)
a=p.parse_args();repo=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(a.workspace/'tools/python_deps'))
from research_audio_review_v1 import build
r=build(a.workspace,a.input,a.audit,a.out,repo/'tools/idle_local_partition_v1/review.html',
        'finite_idle_joint_budget_pending_audit',Path(__file__))
print(dict(result=r['result'],clips=len(r['clips']),gain=r['common_gain'],url=r['url']),flush=True)
