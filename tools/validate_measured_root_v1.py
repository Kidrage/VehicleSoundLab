"""Qualify one measured-root refinement candidate on all original and additional controls."""
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
import scipy
from drive_evidence_v1.sources import sha
from shift_evidence_v1.spectrum import observe
from exterior_clock_v1.warp import render_positions
from measured_root_v1.coarse import track
from fractional_clock_v1.coordinate import warp
from fractional_clock_v1.phase import refine,diagnostics
from fractional_clock_v1.measure import moments,coherent_moments,compare
from fractional_clock_v1.fixtures import make
from fractional_clock_v1.projection import analytic_check


def save(path,value):
    path.write_text(json.dumps(value,indent=2,allow_nan=False)+'\n',encoding='utf-8',newline='\n')


args.out.mkdir(parents=True,exist_ok=False)
report=dict(schema='vsl.measured-root-validation/1',result='running',cases=[],sources={},
    real_source_evaluated=False,model_exported=False,runtime_modified=False,
    environment=dict(python=sys.version,numpy=np.__version__,scipy=scipy.__version__))
try:
    plan_path=repo/'research/measured_root_v1_plan.json'
    plan=json.loads(plan_path.read_text(encoding='utf-8'))
    report['plan_sha256']=sha(plan_path)
    sources=[Path(__file__),plan_path,repo/'tools/drive_evidence_v1/sources.py',
        repo/'tools/shift_evidence_v1/spectrum.py',repo/'tools/state_colour_v2/clock.py',
        repo/'tools/exterior_clock_v1/warp.py',repo/'tools/multicarrier_clock_v1/coarse.py',
        repo/'tools/multicarrier_clock_v1/fixtures.py',repo/'tools/measured_root_v1/coarse.py',repo/'tools/measured_root_v1/__init__.py']+list((repo/'tools/fractional_clock_v1').glob('*.py'))
    for source in sources:
        relative=source.relative_to(repo)
        target=args.out/'exact_sources'/relative
        target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(source,target)
        report['sources'][relative.as_posix()]=sha(source)
    cycle=plan['coordinate']['samples_per_coarse_cycle']
    if plan['phase'].get('projection_mode')=='local_joint':
        report['analytic_joint_projection']=analytic_check(cycle,plan['phase'],plan['coordinate']['fractional_denominator'])
    for case in plan['fixtures']:
        item=dict(case=case,status='running',supports_profile=False)
        directory=args.out/case['id']
        directory.mkdir()
        audio,t,true_phase,true_frequency=make(case,plan['seconds'])
        observed=observe(audio,0,plan['coarse']['window_ms'],hop=plan['coarse']['hop_samples'])
        path=track(observed,*plan['selected_seconds'],case['root_hz'],plan['coarse'])
        item['track_status']=path['status']
        save(directory/'coarse.json',path)
        if path['rows']:
            times=np.array([row['seconds'] for row in path['rows']])
            roots=np.array([row['root_hz'] for row in path['rows']])
            truth=np.interp(times,t,true_frequency)
            item['coarse_relative_root_p95']=float(np.percentile(abs(roots-truth)/truth,95))
            try:
                normalized,positions,cutoff=warp(audio,0,times,roots,*plan['selected_seconds'],plan['coordinate'])
                normalized,positions,phase=refine(audio,0,normalized,positions,cutoff,plan['coordinate'],plan['phase'])
                inferred=1/(cycle*np.diff(positions))
                truth=np.interp((positions[1:]+positions[:-1])/2,t,true_frequency)
                root_error=float(np.percentile(abs(inferred-truth)/truth,95))
                origin=float(np.interp(positions[0],t,true_phase))
                oracle_positions=np.interp(origin+np.arange(len(positions))/cycle,true_phase,t)
                oracle=render_positions(audio,0,oracle_positions,phase['source_cutoff_hz'])
                delta=compare(moments(oracle,cycle,case['root_hz'],plan['bands_hz'],plan['power_window_coarse_cycles']),
                    moments(normalized,cycle,case['root_hz'],plan['bands_hz'],plan['power_window_coarse_cycles']))
                coherent=compare(coherent_moments(oracle,cycle,case['root_hz'],plan['bands_hz'],
                    plan['coherent_power_window_coarse_cycles'],plan['coordinate']['fractional_denominator']),
                    coherent_moments(normalized,cycle,case['root_hz'],plan['bands_hz'],
                    plan['coherent_power_window_coarse_cycles'],plan['coordinate']['fractional_denominator']))
                independent=diagnostics(normalized,cycle,plan['heldout_orders'],plan['heldout_projection_cycles'],plan['rules'])
                rules=plan['rules']
                passed=bool(root_error<=rules['maximum_root_relative_p95'] and
                    delta['maximum_band_power_error_db']<=rules['maximum_oracle_band_power_error_db'] and
                    delta['maximum_complex_correlation_error']<=rules['maximum_oracle_complex_correlation_error'] and
                    coherent['maximum_band_power_error_db']<=rules['maximum_oracle_band_power_error_db'] and
                    coherent['maximum_complex_correlation_error']<=rules['maximum_oracle_complex_correlation_error'] and
                    independent['passed'])
                item.update(status='measured',phase=phase,root_relative_p95=root_error,oracle=delta,
                    coherent_oracle=coherent,independent_agreement=independent,supports_profile=passed,
                    retained_seconds=[float(positions[0]),float(positions[-1])],retained_coarse_cycles=len(positions)/cycle)
                np.savez_compressed(directory/'coordinates.npz',source_seconds=positions)
            except ValueError as exc:
                item.update(status='phase_rejected',reason=str(exc))
        else:
            item['status']='coarse_rejected'
        item['passed']=not item['supports_profile'] if case.get('negative') else item['supports_profile']
        report['cases'].append(item)
        save(directory/'report.json',item)
        print(json.dumps(dict(id=case['id'],status=item['status'],passed=item['passed'],root_error=item.get('root_relative_p95'),
            power_db=item.get('oracle',{}).get('maximum_band_power_error_db'),
            coherent_power_db=item.get('coherent_oracle',{}).get('maximum_band_power_error_db'),
            stereo_error=item.get('oracle',{}).get('maximum_complex_correlation_error'),reason=item.get('reason'))),flush=True)
    report['result']='passed' if all(row['passed'] for row in report['cases']) else 'rejected'
    report['real_source_permitted']=report['result']=='passed'
except Exception as exc:
    report.update(result='failed',error=repr(exc),real_source_permitted=False)
    raise
finally:
    save(args.out/'report.json',report)
