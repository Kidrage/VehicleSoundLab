"""Reuse exact HF evidence only after saved-coordinate and source identity checks."""
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
from drive_evidence_v1.sources import sha
from fractional_clock_v1.fixtures import make
from fractional_clock_v1.phase import project
from exterior_clock_v1.warp import render_positions


def load(path):
    return json.loads(path.read_text(encoding='utf-8'))


def save(path,value):
    path.write_text(json.dumps(value,indent=2,allow_nan=False)+'\n',encoding='utf-8',newline='\n')


def lines(audio,cycle,orders):
    _,values,_=project(audio,cycle,orders,20,.25)
    power=np.mean(abs(values)**2,axis=0)/2
    cross=np.mean(values[:,:,0]*np.conj(values[:,:,1]),axis=0)/2
    return power,cross/np.sqrt(np.maximum(power.prod(axis=1),1e-60))


args.out.mkdir(parents=True,exist_ok=False)
report=dict(schema='vsl.supported-root-hf-audit/1',result='running',sources={},cases=[],
    real_source_evaluated=False,model_exported=False,runtime_modified=False)
try:
    current=args.workspace/'references/analysis/supported_root_v1/validate1'
    old=args.workspace/'references/analysis/measured_root_v1/validate1'
    previous_audit=args.workspace/'references/analysis/measured_root_v1/high_audit1'
    validation=load(current/'report.json')
    previous=load(old/'report.json')
    audit=load(previous_audit/'report.json')
    assert validation['result'] in ('passed','rejected') and not validation['subset']
    assert [row['case'] for row in validation['cases']]==[row['case'] for row in previous['cases']]
    assert audit['validation_report_sha256']==sha(old/'report.json')
    plan_path=repo/'research/supported_root_v1_plan.json'
    plan=load(plan_path)
    assert validation['plan_sha256']==sha(plan_path)
    old_plan=load(previous_audit/'exact_sources/research/measured_root_v1_plan.json')
    for key in ('fixtures','seconds','coordinate','bands_hz','rules','power_window_coarse_cycles','coherent_power_window_coarse_cycles'):
        assert plan[key]==old_plan[key]
    for name,digest in validation['sources'].items():
        assert sha(repo/name)==sha(current/'exact_sources'/name)==digest
    # Only the unchanged fixture and resampler determine the waveform once
    # positions are equal. Coarse estimator identity is allowed to change.
    for name in ('tools/fractional_clock_v1/fixtures.py','tools/multicarrier_clock_v1/fixtures.py',
                 'tools/exterior_clock_v1/warp.py','tools/fractional_clock_v1/phase.py'):
        assert sha(repo/name)==sha(previous_audit/'exact_sources'/name)==audit['sources'][name]
    sources=[Path(__file__)]+[repo/name for name in validation['sources']]
    for source in sources:
        target=args.out/'exact_sources'/source.relative_to(repo)
        target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(source,target)
        report['sources'][source.relative_to(repo).as_posix()]=sha(source)
    report.update(validation_report_sha256=sha(current/'report.json'),prior_HF_audit_report_sha256=sha(previous_audit/'report.json'))
    for case in validation['cases']:
        name=case['case']['id']
        if case['status']!='measured':
            report['cases'].append(dict(case=case['case'],hf_measured=False,passed=case['passed'],status=case['status']))
            continue
        first=next(row for row in previous['cases'] if row['case']['id']==name)
        prior=next(row for row in audit['cases'] if row['case']['id']==name)
        current_npz=current/name/'coordinates.npz'
        old_npz=old/name/'coordinates.npz'
        with np.load(current_npz,allow_pickle=False) as archive:
            positions=archive['source_seconds']
        old_positions=None
        if first['status']=='measured':
            with np.load(old_npz,allow_pickle=False) as archive:
                old_positions=archive['source_seconds']
            assert case['phase']['source_cutoff_hz']==first['phase']['source_cutoff_hz']
        equal=old_positions is not None and np.array_equal(positions,old_positions)
        if equal:
            row=dict(prior,evidence='reused_exact_waveform_coordinate_and_source_identity')
        else:
            audio,time,truth,frequency=make(case['case'],plan['seconds'])
            orders=sorted(set(int(hz/max(frequency)) for hz in (12000,13500)))
            cycle=plan['coordinate']['samples_per_coarse_cycle']
            origin=np.interp(positions[0],time,truth)
            ideal_at=np.interp(origin+np.arange(len(positions))/cycle,truth,time)
            cutoff=case['phase']['source_cutoff_hz']
            power,corr=lines(render_positions(audio,0,positions,cutoff),cycle,orders)
            expected,expected_corr=lines(render_positions(audio,0,ideal_at,cutoff),cycle,orders)
            delta=10*np.log10(np.maximum(power,1e-30)/np.maximum(expected,1e-30))
            correlation=abs(corr-expected_corr)
            row=dict(case=case['case'],hf_measured=True,status='measured',orders=orders,
                power_difference_db_LR=delta.tolist(),complex_correlation_difference=correlation.tolist(),
                maximum_line_power_error_db=float(abs(delta).max()),maximum_line_correlation_error=float(correlation.max()),
                passed=bool(abs(delta).max()<=plan['rules']['maximum_oracle_band_power_error_db'] and
                    correlation.max()<=plan['rules']['maximum_oracle_complex_correlation_error']),evidence='fresh_HF_measurement')
        row.update(coordinates_equal=bool(equal),new_coordinates_sha256=sha(current_npz),old_coordinates_sha256=sha(old_npz) if old_positions is not None else None,
            coordinate_float64_sha256=hashlib.sha256(positions.astype('<f8').tobytes()).hexdigest())
        report['cases'].append(row)
    measured=[row for row in report['cases'] if row['hf_measured']]
    report.update(result='passed' if all(row['passed'] for row in report['cases']) else 'rejected',
        measured_HF_all_passed=all(row['passed'] for row in measured),
        reused_HF_cases=sum(row['coordinates_equal'] for row in measured),
        fresh_HF_cases=sum(not row['coordinates_equal'] for row in measured),
        combined_qualification_passed=validation['result']=='passed' and all(row['passed'] for row in report['cases']))
    print(json.dumps({key:report[key] for key in ('result','measured_HF_all_passed','reused_HF_cases','fresh_HF_cases','combined_qualification_passed')}),flush=True)
except Exception as exc:
    report.update(result='failed',error=repr(exc),combined_qualification_passed=False)
    raise
finally:
    save(args.out/'report.json',report)
