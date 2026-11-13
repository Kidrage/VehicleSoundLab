"""Joint local frequency observations with independently qualified neighbor compensation."""
import argparse
import json
import math
from pathlib import Path
import shutil
import sys

p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--workspace',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
args=p.parse_args();repo=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(args.workspace/'tools/python_deps'))
import numpy as np
from drive_evidence_v1.sources import read,sha
from line_motion_v1.local_chirps import local_chirps
from line_motion_v1.peak_controls import peak_controls
from line_motion_v1.moments import group_observation

def load(path):return json.loads(path.read_text(encoding='utf-8'))
def serial(value):
    if isinstance(value,np.ndarray):return serial(value.tolist())
    if isinstance(value,dict):return {k:serial(v) for k,v in value.items()}
    if isinstance(value,list):return [serial(x) for x in value]
    if isinstance(value,float) and not math.isfinite(value):return None
    return value

args.out.mkdir(parents=True,exist_ok=False)
report=dict(schema='vsl.F2-local-chirps/1',result='running',sources={},real_audio_read=False,
    shared_phase_clock_fit=False,local_independent_phase_nuisance_fit=True,model_exported=False,runtime_changed=False)
try:
    prior_path=args.workspace/'references/analysis/F2_line_motion_v1/observe2/report.json';prior=load(prior_path)
    files=[Path(__file__),repo/'research/F2_local_chirps_v1_plan.json',repo/'tools/drive_evidence_v1/sources.py',
           repo/'references/segments_v1.json',*sorted((repo/'tools/line_motion_v1').glob('*.py'))]
    for path in files:
        relative=path.relative_to(repo);target=args.out/'exact_sources'/relative
        target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(path,target)
        report['sources'][relative.as_posix()]=sha(path)
    checked=peak_controls(observer=local_chirps);report['controls']=checked
    assert checked['passed'],'No recording read before fixed known controls pass'
    audio,provenance=read(args.workspace,'F2_tailpipe','fixed_window_spectral_observation');report['real_audio_read']=True
    rows=[];numbers=[]
    for old in prior['observations']:
        start=round((old['source_seconds'][0]-6)*48000)
        measured=local_chirps(audio[start:start+48000],48000,old['nominal_Hz'])
        group=group_observation(measured['frequency_Hz'])
        rows.append(dict(source_seconds=old['source_seconds'],original_nominal_Hz=old['nominal_Hz'],
            measured=serial({k:v for k,v in measured.items() if k not in ('moment','derivative_moment')}),
            exploratory_group=serial(group),all_anchor_fits_eligible=bool(measured['fit_eligible'][:3].all()),
            previous_all_anchor_roots_resolved=old['all_anchor_roots_resolved']))
        numbers.append(measured)
        print(json.dumps(dict(seconds=old['source_seconds'],eligible=rows[-1]['all_anchor_fits_eligible'],
            fit=[dict(success=x['success'],n=x.get('function_evaluations')) for x in measured['local_chirp_fit']])),flush=True)
    np.savez_compressed(args.out/'observations.npz',audio=audio,
        **{key:np.stack([x[key] for x in numbers]) for key,value in numbers[0].items() if isinstance(value,np.ndarray)})
    counts=dict(observations=90,eligible_frequencies=sum(int(x['fit_eligible'].sum()) for x in numbers),
        complete_anchor_rows=sum(r['all_anchor_fits_eligible'] for r in rows))
    report.update(result='F2_joint_local_chirp_frequencies_measured_not_common_phase_or_idle_DNA',
        provenance=provenance,prior_report_sha256=sha(prior_path),observations=rows,counts=counts,
        arrays_sha256=sha(args.out/'observations.npz'),selected_fundamental=None,RPM_inferred=False,
        complete_continuous_phase_established=False,phase_extracted_real_model_permitted=False,
        limits=['Independent local phase/amplitude nuisance fits are not a shared engine clock or exported oscillator model',
            'Local chirp/constant amplitude assumptions can be wrong for real recordings; fit convergence is not confidence or source separation',
            'Native peak cells/order hypotheses selected from earlier data remain exploratory',
            'No recorded timeline replay, new synthesized audio, DNA export or runtime/C change'])
    print(json.dumps(dict(result=report['result'],counts=counts,controls=checked)),flush=True)
except Exception as exc:report.update(result='failed',error=repr(exc));raise
finally:(args.out/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8',newline='\n')
