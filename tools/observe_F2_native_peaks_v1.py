"""Observe F2 native per-window peaks with explicit source-identity limitations."""
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
from line_motion_v1.peaks import native_peaks
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
report=dict(schema='vsl.F2-native-peaks/1',result='running',sources={},real_audio_read=False,
    phase_estimator_run=False,model_exported=False,runtime_changed=False)
try:
    plan=load(repo/'research/F2_native_peaks_v1_plan.json')
    prior_path=args.workspace/'references/analysis/F2_line_motion_v1/observe2/report.json'
    prior=load(prior_path)
    files=[Path(__file__),repo/'research/F2_native_peaks_v1_plan.json',repo/'tools/drive_evidence_v1/sources.py',
           repo/'references/segments_v1.json',*sorted((repo/'tools/line_motion_v1').glob('*.py'))]
    for path in files:
        relative=path.relative_to(repo);target=args.out/'exact_sources'/relative
        target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(path,target)
        report['sources'][relative.as_posix()]=sha(path)
    checked=peak_controls();report['controls']=checked
    assert checked['passed'],'No recording read before known controls pass'
    audio,provenance=read(args.workspace,'F2_tailpipe','fixed_window_spectral_observation')
    report['real_audio_read']=True
    rows=[];numbers=[]
    for old in prior['observations']:
        start=round((old['source_seconds'][0]-6)*48000)
        measured=native_peaks(audio[start:start+48000],48000,old['nominal_Hz'])
        group=group_observation(measured['frequency_Hz'])
        rows.append(dict(source_seconds=old['source_seconds'],original_nominal_Hz=old['nominal_Hz'],
            measured=serial({k:v for k,v in measured.items() if k not in ('moment','derivative_moment')}),
            exploratory_group=serial(group),
            all_anchor_roots_resolved=bool(measured['root_resolved'][:3].all() and measured['supported'][:3].all()),
            previous_all_anchor_roots_resolved=old['all_anchor_roots_resolved']))
        numbers.append(measured)
    np.savez_compressed(args.out/'observations.npz',audio=audio,
        **{key:np.stack([x[key] for x in numbers]) for key in numbers[0] if key!='candidates'})
    complete=sum(r['all_anchor_roots_resolved'] for r in rows)
    counts=dict(observations=90,resolved=sum(int(x['root_resolved'].sum()) for x in numbers),
        unresolved=sum(int((~x['root_resolved']).sum()) for x in numbers),complete_anchor_rows=complete)
    report.update(result='F2_native_window_peak_centers_observed_not_phase_or_single_source_qualification',
        provenance=provenance,prior_report_sha256=sha(prior_path),observations=rows,counts=counts,
        arrays_sha256=sha(args.out/'observations.npz'),selected_fundamental=None,RPM_inferred=False,
        complete_continuous_phase_established=False,phase_extracted_real_model_permitted=False,
        limits=['One spectral maximum may be a mixture of unresolved components; known two-tone counterexample retained',
            'Cells and order hypotheses are exploratory and based on the previously seen spectrum',
            'Frequency center agreement does not qualify common phase, physical period, engine/wind separation or RPM',
            'Do not convert nine local observations into an interpolated phase clock or new DNA'])
    print(json.dumps(dict(result=report['result'],counts=counts,controls=checked)),flush=True)
except Exception as exc:report.update(result='failed',error=repr(exc));raise
finally:(args.out/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8',newline='\n')
