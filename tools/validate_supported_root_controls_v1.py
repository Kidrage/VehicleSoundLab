"""Qualify support geometry with independent scalar and closed-form oracles."""
import argparse
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
from drive_evidence_v1.sources import sha
from supported_root_v1.feasible import project


def scalar_supported(frequencies,root,orders):
    used=set()
    count=0
    for order in orders:
        if not len(frequencies):
            break
        frequency=min(frequencies,key=lambda item:abs(item-root*order))
        wanted=root*order
        if 35<=wanted<1200 and abs(wanted-frequency)<=max(6,.025*wanted) and frequency not in used:
            count+=1
            used.add(frequency)
    return count


def save(path,value):
    path.write_text(json.dumps(value,indent=2,allow_nan=False)+'\n',encoding='utf-8',newline='\n')


args.out.mkdir(parents=True,exist_ok=False)
report=dict(schema='vsl.supported-root-controls/1',result='running',sources={},cases=[],real_audio_read=False)
try:
    plan_path=repo/'research/supported_root_controls_v1_plan.json'
    plan=json.loads(plan_path.read_text(encoding='utf-8'))
    sources=[Path(__file__),plan_path,repo/'tools/supported_root_v1/feasible.py',
        repo/'tools/supported_root_v1/__init__.py',repo/'tools/drive_evidence_v1/sources.py']
    for source in sources:
        target=args.out/'exact_sources'/source.relative_to(repo)
        target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(source,target)
        report['sources'][source.relative_to(repo).as_posix()]=sha(source)
    fixed=[
        ('identity',[100,150,250],[2,3,5],50,50),
        ('closed_upper',[100,150,250],[2,3,5],55,250/(.975*5)),
        ('closed_lower',[100,150,250],[2,3,5],40,250/(1.025*5)),
        ('outside_range',[100,150,250],[2,3,5],100,250/(.975*5)),
        ('included35',[35,52.5,87.5],[2,3,5],15,17.5),
        ('interpolated_below35',[34.8,52.5,87.5],[2,3,5],15,17.5),
        ('excluded1200',[120,180,1199],[2,3,20],60,np.nextafter(60.,0)),
        ('interpolated_above1200',[120,180,1200.2],[2,3,20],60,np.nextafter(60.,0)),
        ('duplicate_peak',[100,100,100],[2,3,5],40,None),
        ('two_peaks',[100,150],[2,3,5],40,None),
        ('no_peaks',[],[2,3,5],40,None)]
    for name,frequencies,orders,proposal,expected in fixed:
        item=dict(id=name,expected_reject=expected is None)
        try:
            result,proof=project(proposal,frequencies,orders,plan['root_range_hz'])
            assert expected is not None
            assert abs(result-expected)<=plan['maximum_closed_form_error_hz']
            assert scalar_supported(sorted(set(frequencies)),result,orders)>=3
            item.update(result_hz=result,closed_form_error_hz=float(abs(result-expected)),proof=proof,passed=True)
        except ValueError as exc:
            assert expected is None
            item.update(reason=str(exc),passed=True)
        report['cases'].append(item)
    rng=np.random.default_rng(plan['random_seed'])
    orders=np.array([2,3,5,7,10,15,20])
    grid=np.linspace(*plan['root_range_hz'],plan['independent_grid_points'])
    for index in range(plan['random_cases']):
        root=rng.uniform(18,75)
        frequencies=np.r_[root*orders+rng.normal(0,1.5,len(orders)),rng.uniform(35,1200,9)]
        frequencies=np.unique(frequencies[(frequencies>=35)&(frequencies<1200)])
        proposal=float(root+rng.uniform(-18,18))
        result,proof=project(proposal,frequencies,orders,plan['root_range_hz'])
        assert scalar_supported(frequencies,result,orders)>=3
        feasible_grid=np.array([value for value in grid if scalar_supported(frequencies,value,orders)>=3])
        assert len(feasible_grid)
        grid_distance=float(min(abs(feasible_grid-proposal)))
        assert abs(result-proposal)<=grid_distance+1e-10
        identity,identity_proof=project(result,frequencies,orders,plan['root_range_hz'])
        assert identity==result and not identity_proof['projected']
        reversed_result,_=project(proposal,frequencies[::-1],orders,plan['root_range_hz'])
        assert reversed_result==result
        report['cases'].append(dict(id=f'random_{index}',passed=True,result_hz=result,
            projection_distance_hz=float(abs(result-proposal)),independent_grid_distance_hz=grid_distance,proof=proof))
    report['result']='passed'
    print(json.dumps(dict(result='passed',cases=len(report['cases']))),flush=True)
except Exception as exc:
    report.update(result='failed',error=repr(exc))
    raise
finally:
    save(args.out/'report.json',report)
