"""Independent numerical contracts for the aperture-aware risk selector."""
import argparse
from contextlib import nullcontext
import json
from pathlib import Path
import shutil
import sys

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--workspace',type=Path,required=True)
parser.add_argument('--out',type=Path,required=True)
args=parser.parse_args()
repo=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(args.workspace/'tools/python_deps'))
from drive_evidence_v1.sources import sha
from smooth_envelope_v1.covariance_checks import controls as covariance_controls
from smooth_envelope_v1.sure_checks import controls as risk_controls
try:
    from threadpoolctl import threadpool_limits
    limit=lambda:threadpool_limits(limits=2)
except ImportError:
    limit=nullcontext
args.out.mkdir(parents=True,exist_ok=False)
report=dict(schema='vsl.smooth-envelope-sure-controls/1',result='running',sources={},real_audio_read=False)
try:
    sources={Path(__file__),repo/'research/aperture_model_v1_plan.json',repo/'tools/aperture_model_v1/forward.py',
        repo/'tools/drive_evidence_v1/sources.py'}|set((repo/'tools/smooth_envelope_v1').glob('*.py'))
    for source in sources:
        relative=source.relative_to(repo)
        target=args.out/'exact_sources'/relative
        target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(source,target)
        report['sources'][relative.as_posix()]=sha(source)
    plan=json.loads((repo/'research/aperture_model_v1_plan.json').read_text(encoding='utf-8'))
    with limit():
        report['covariance']=covariance_controls(plan)
        report['predictive_risk']=risk_controls(plan)
    report['result']='passed'
    print(json.dumps(dict(result=report['result'],covariance=report['covariance'],risk=report['predictive_risk'])),flush=True)
except Exception as exc:
    report.update(result='failed',error=repr(exc))
    raise
finally:
    (args.out/'report.json').write_text(json.dumps(report,indent=2,allow_nan=False)+'\n',encoding='utf-8',newline='\n')
