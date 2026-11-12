"""Check known individual HF lines in a saved candidate's full mixtures."""
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
from exterior_clock_v1.warp import render_positions
from fractional_clock_v1.fixtures import make
from fractional_clock_v1.phase import project


def load(path):
    return json.loads(path.read_text(encoding='utf-8'))


def save(path,value):
    path.write_text(json.dumps(value,indent=2,allow_nan=False)+'\n',encoding='utf-8',newline='\n')


def lines(audio,cycle,orders,task):
    _,z,_=project(audio,cycle,orders,task['projection_coarse_cycles'],task['projection_hop_coarse_cycles'])
    power=np.mean(abs(z)**2,axis=0)/2
    cross=np.mean(z[:,:,0]*np.conj(z[:,:,1]),axis=0)/2
    return power,cross/np.sqrt(np.maximum(power.prod(axis=1),1e-60))


args.out.mkdir(parents=True,exist_ok=False)
report=dict(schema='vsl.measured-root-high-audit/1',result='running',sources={},cases=[],
    real_source_evaluated=False,model_exported=False,runtime_modified=False)
try:
    task_path=repo/'research/measured_root_high_v1_plan.json'
    task=load(task_path)
    validated=args.workspace/task['validation']
    prior=load(validated/'report.json')
    assert prior['result'] in ('passed','rejected')
    plan_path=repo/'research/measured_root_v1_plan.json'
    plan=load(plan_path)
    assert prior['plan_sha256']==sha(plan_path)
    assert [item['case'] for item in prior['cases']]==plan['fixtures']
    for name,digest in prior['sources'].items():
        assert sha(repo/name)==sha(validated/'exact_sources'/name)==digest
    sources=[Path(__file__),task_path]+[repo/name for name in prior['sources']]
    for source in sources:
        target=args.out/'exact_sources'/source.relative_to(repo)
        target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(source,target)
        report['sources'][source.relative_to(repo).as_posix()]=sha(source)
    report['validation_report_sha256']=sha(validated/'report.json')
    baseline=args.workspace/task['baseline_validation']
    baseline_report=load(baseline/'report.json')
    report['baseline_validation_report_sha256']=sha(baseline/'report.json')
    for case in prior['cases']:
        if case['status']!='measured':
            report['cases'].append(dict(case=case['case'],status=case['status'],passed=case['passed'],
                hf_measured=False,reason=case.get('reason')))
            continue
        audio,time,truth,frequency=make(case['case'],plan['seconds'])
        orders=sorted(set(int(target/max(frequency)) for target in task['highest_physical_hz_targets']))
        saved=validated/case['case']['id']/'coordinates.npz'
        with np.load(saved,allow_pickle=False) as archive:
            positions=archive['source_seconds']
        cycle=plan['coordinate']['samples_per_coarse_cycle']
        origin=np.interp(positions[0],time,truth)
        ideal_positions=np.interp(origin+np.arange(len(positions))/cycle,truth,time)
        cutoff=case['phase']['source_cutoff_hz']
        measured=render_positions(audio,0,positions,cutoff)
        ideal=render_positions(audio,0,ideal_positions,cutoff)
        power,corr=lines(measured,cycle,orders,task)
        expected,expected_corr=lines(ideal,cycle,orders,task)
        delta=10*np.log10(np.maximum(power,1e-30)/np.maximum(expected,1e-30))
        correlation=abs(corr-expected_corr)
        passed=bool(abs(delta).max()<=task['maximum_line_power_error_db'] and
            correlation.max()<=task['maximum_line_complex_correlation_error'])
        item=dict(case=case['case'],status='measured',hf_measured=True,passed=passed,orders=orders,
            coordinates_sha256=sha(saved),power_difference_db_LR=delta.tolist(),
            complex_correlation_difference=correlation.tolist(),maximum_line_power_error_db=float(abs(delta).max()),
            maximum_line_correlation_error=float(correlation.max()))
        if case['case']['id'] in task['baseline_cases']:
            old=next(row for row in baseline_report['cases'] if row['case']['id']==case['case']['id'])
            assert old['case']==case['case'] and old['status']=='measured'
            old_saved=baseline/case['case']['id']/'coordinates.npz'
            with np.load(old_saved,allow_pickle=False) as archive:
                old_positions=archive['source_seconds']
            old_origin=np.interp(old_positions[0],time,truth)
            old_ideal=np.interp(old_origin+np.arange(len(old_positions))/cycle,truth,time)
            old_power,old_corr=lines(render_positions(audio,0,old_positions,cutoff),cycle,orders,task)
            old_expected,old_expected_corr=lines(render_positions(audio,0,old_ideal,cutoff),cycle,orders,task)
            old_delta=10*np.log10(np.maximum(old_power,1e-30)/np.maximum(old_expected,1e-30))
            item['baseline_full_mixture']=dict(coordinates_sha256=sha(old_saved),
                power_difference_db_LR=old_delta.tolist(),complex_correlation_difference=abs(old_corr-old_expected_corr).tolist(),
                maximum_line_power_error_db=float(abs(old_delta).max()))
        report['cases'].append(item)
        print(json.dumps(dict(id=case['case']['id'],passed=passed,power_db=item['maximum_line_power_error_db'],
            stereo_error=item['maximum_line_correlation_error'])),flush=True)
    report['result']='passed' if all(row['passed'] for row in report['cases']) else 'rejected'
    report['combined_qualification_passed']=bool(prior['result']=='passed' and report['result']=='passed')
except Exception as exc:
    report.update(result='failed',error=repr(exc),combined_qualification_passed=False)
    raise
finally:
    save(args.out/'report.json',report)
