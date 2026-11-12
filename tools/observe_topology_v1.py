"""Evaluate measured topology first, without fitting or reading real recordings."""
import argparse
import hashlib
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
import numpy as np
import scipy
from drive_evidence_v1.sources import sha
from observed_topology_v1.discover import discover
from observed_topology_v1.fixtures import make
from observed_topology_v1.checks import controls
from observed_topology_v1.inputs import numerical_inputs


def save(path,value):
    path.write_text(json.dumps(value,indent=2,allow_nan=False)+'\n',encoding='utf-8',newline='\n')


args.out.mkdir(parents=True,exist_ok=False)
report=dict(schema='vsl.observed-topology-observation/1',result='running',cases=[],sources={},
    real_audio_read=False,estimator_rerun=False,real_source_permitted=False,
    environment=dict(numpy=np.__version__,scipy=scipy.__version__,python=sys.version))
try:
    settings_path=repo/'research/observed_topology_v1_plan.json'
    settings=json.loads(settings_path.read_text(encoding='utf-8'))
    base_path=repo/settings['base_plan']
    assert sha(base_path)==settings['base_plan_sha256']
    base=json.loads(base_path.read_text(encoding='utf-8'))
    minority_path=repo/settings['minority_plan']
    minority=json.loads(minority_path.read_text(encoding='utf-8'))
    geometry,discovery_settings=numerical_inputs(base,settings)
    sources=[Path(__file__),settings_path,base_path,minority_path,repo/'tools/drive_evidence_v1/sources.py']
    for module in ('aperture_model_v1','minority_phase_v1','observed_topology_v1'):
        sources+=list((repo/'tools'/module).glob('*.py'))
    for source in sources:
        relative=source.relative_to(repo)
        target=args.out/'exact_sources'/relative
        target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(source,target)
        report['sources'][relative.as_posix()]=sha(source)
    report['controls']=controls(geometry,discovery_settings)
    assert report['controls']['passed']
    for case in base['cases']+minority['added_cases']+settings['added_cases']:
        time,audio,truth,fixture_plan=make(case,base)
        orders,evidence=discover(audio,time,geometry,discovery_settings)
        expected=[5] if case.get('single') else fixture_plan['source_orders']
        item=dict(case=case,evidence=evidence,fixture_orders=expected,
            exact_topology=orders==expected,fixture_audio_sha256=hashlib.sha256(audio.tobytes()).hexdigest(),
            missing=[value for value in expected if value not in orders],extra=[value for value in orders if value not in expected])
        directory=args.out/case['id']
        directory.mkdir()
        save(directory/'report.json',item)
        report['cases'].append(item)
        print(json.dumps(dict(id=case['id'],inferred=len(orders),expected=len(expected),
            missing=item['missing'],extra=item['extra'])),flush=True)
    report['result']='observed'
except Exception as exc:
    report.update(result='failed',error=repr(exc))
    raise
finally:
    save(args.out/'report.json',report)
