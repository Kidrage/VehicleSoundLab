"""Explain a rejected measured-median proposal, without changing the estimator."""
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
from fractional_clock_v1.fixtures import make
from shift_evidence_v1.spectrum import observe
from multicarrier_clock_v1.coarse import track
from measured_root_v1.coarse import selected_lines


def save(path,value):
    path.write_text(json.dumps(value,indent=2,allow_nan=False)+'\n',encoding='utf-8',newline='\n')


args.out.mkdir(parents=True,exist_ok=False)
report=dict(schema='vsl.measured-root-rapid-diagnosis/1',result='running',sources={},
    real_source_evaluated=False,model_exported=False,runtime_modified=False)
try:
    validation_path=args.workspace/'references/analysis/measured_root_v1/validate1/report.json'
    validation=json.loads(validation_path.read_text(encoding='utf-8'))
    plan=json.loads((repo/'research/measured_root_v1_plan.json').read_text(encoding='utf-8'))
    case=next(row['case'] for row in validation['cases'] if row['case']['id']=='fifth_rapid_corner')
    assert next(row for row in validation['cases'] if row['case']==case)['track_status']=='unsupported_measured_median'
    for name,digest in validation['sources'].items():
        assert sha(repo/name)==sha(validation_path.parent/'exact_sources'/name)==digest
    sources=[Path(__file__)]+[repo/name for name in validation['sources']]
    for source in sources:
        target=args.out/'exact_sources'/source.relative_to(repo)
        target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(source,target)
        report['sources'][source.relative_to(repo).as_posix()]=sha(source)
    audio,time,phase,frequency=make(case,plan['seconds'])
    observed=observe(audio,0,plan['coarse']['window_ms'],hop=plan['coarse']['hop_samples'])
    path=track(observed,*plan['selected_seconds'],case['root_hz'],plan['coarse'])
    assert path['status']=='measured_consensus'
    selected=np.flatnonzero((observed['seconds']>=plan['selected_seconds'][0]-1e-8)&(observed['seconds']<=plan['selected_seconds'][1]+1e-8))
    failures=[]
    for index,row in zip(selected,path['rows']):
        line,at,prominence=selected_lines(observed['hz'],observed['power_low'][:,index],row['measured_lattice_root_hz'],np.asarray(plan['coarse']['orders']))
        measured=at/line
        weight=line**2*np.clip(prominence/16,.25,1)
        weight=np.minimum(weight,plan['coarse']['precision_weight_median_cap']*np.median(weight))
        order=np.argsort(measured)
        median=measured[order[np.searchsorted(np.cumsum(weight[order]),weight.sum()/2)]]
        supported,_,_=selected_lines(observed['hz'],observed['power_low'][:,index],median,np.asarray(plan['coarse']['orders']))
        if len(supported)<plan['coarse']['minimum_observed_lines']:
            old_supported,_,_=selected_lines(observed['hz'],observed['power_low'][:,index],row['root_hz'],np.asarray(plan['coarse']['orders']))
            failures.append(dict(seconds=row['seconds'],lattice_root_hz=row['measured_lattice_root_hz'],
                original_smoothed_root_hz=row['root_hz'],known_frequency_hz=float(np.interp(row['seconds'],time,frequency)),
                proposal_root_hz=float(median),measured_orders=line.tolist(),measured_peak_frequencies_hz=at.tolist(),
                measured_roots_hz=measured.tolist(),capped_weights=weight.tolist(),proposal_supported_orders=supported.tolist(),
                original_smoothed_supported_orders=old_supported.tolist()))
    assert failures
    report.update(result='diagnosed_no_algorithm_change',validation_report_sha256=sha(validation_path),
        observed_rows=len(selected),unsupported_proposals=failures,
        finding='A median of individually supported peak roots need not remain in their joint support intersection; the proposal is rejected even though an original measured path exists')
    print(json.dumps(dict(result=report['result'],rows=len(selected),unsupported_proposals=len(failures),first=failures[0])),flush=True)
except Exception as exc:
    report.update(result='failed',error=repr(exc))
    raise
finally:
    save(args.out/'report.json',report)
