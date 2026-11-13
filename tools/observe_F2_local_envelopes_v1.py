"""Known constant-AM mismatch and fixed9window affine-envelope comparison."""
import argparse
import json
from pathlib import Path
import shutil
import sys

p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--workspace',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
args=p.parse_args();repo=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(args.workspace/'tools/python_deps'))
import numpy as np
from drive_evidence_v1.sources import read,sha
from line_motion_v1.envelope_controls import controls
from line_motion_v1.local_envelopes import fit_channel,evaluate
from line_motion_v1.local_chirps import evaluate as constant_wave


def load(path):return json.loads(path.read_text(encoding='utf-8'))


args.out.mkdir(parents=True,exist_ok=False)
report=dict(schema='vsl.F2-local-envelopes/1',result='running',sources={},real_audio_read=False,
    shared_phase_clock_fit=False,model_exported=False,runtime_changed=False)
try:
    for path in (Path(__file__),repo/'research/F2_local_envelopes_v1_plan.json',repo/'references/segments_v1.json',
        repo/'tools/drive_evidence_v1/sources.py',*sorted((repo/'tools/line_motion_v1').glob('*.py'))):
        relative=path.relative_to(repo);target=args.out/'exact_sources'/relative;target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(path,target);report['sources'][relative.as_posix()]=sha(path)
    checked=controls();report['controls']=checked
    assert checked['passed'],'Known envelope controls failed; no recording read'
    base=args.workspace/'references/analysis';prior_path=base/'F2_local_chirps_v1/observe1/report.json';prior=load(prior_path)
    counter_path=base/'F2_peak_identity_v1/observe1/report.json';counter=load(counter_path)
    assert counter['prior_report_sha256']==sha(prior_path)
    audio,provenance=read(args.workspace,'F2_tailpipe','fixed_window_spectral_observation');report['real_audio_read']=True
    t=np.arange(48000)/48000-.5;rows=[];old_waves=[];new_waves=[]
    for i,row in enumerate(prior['observations']):
        start=round((row['source_seconds'][0]-6)*48000);part=audio[start:start+48000]
        fits=[];before=[];after=[]
        for ch in range(2):
            constant=counter['counterfactual'][ch]['fit'] if i==1 else row['measured']['local_chirp_fit'][ch]
            nominal=np.array(constant['nominal_Hz']);old=np.array(constant['fitted_parameters']);m=len(nominal)
            value,fit=fit_channel(part[:,ch],48000,nominal)
            fits.append(dict(channel=ch,constant_source='F2_peak_identity_v1/observe1' if i==1 else 'F2_local_chirps_v1/observe1',
                constant_fit=constant,affine_fit=fit,cost_reduction_fraction=1-fit['cost']/constant['cost'],
                main_frequency_change_Hz=(value[:3]-old[:3]).tolist(),
                main_chirp_change_Hz_per_s=(value[m:m+3]-old[m:m+3]).tolist()))
            before.append(constant_wave(old,nominal,t)[0]);after.append(evaluate(value,nominal,t)[0])
        rows.append(dict(source_seconds=row['source_seconds'],fits=fits))
        old_waves.append(np.column_stack(before));new_waves.append(np.column_stack(after))
    np.savez_compressed(args.out/'observations.npz',audio=audio,before=np.stack(old_waves),after=np.stack(new_waves))
    report.update(result='fixed9window_positive_affine_envelopes_observed_not_idle_DNA',
        provenance=provenance,prior_report_sha256=sha(prior_path),counterfactual_report_sha256=sha(counter_path),
        observations=rows,arrays_sha256=sha(args.out/'observations.npz'),phase_extracted_real_model_permitted=False,RPM_inferred=False,
        limits=['Same local component inventories compare constant versus affine amplitudes, not full source recovery',
            'One slope bounded to +/-1/s preserves positivity; saturation and unresolved frequencies remain explicit',
            'Independent local phases do not establish an engine clock or physical speed/load',
            'Training loss decreases and within-bound flags cannot certify recording completeness or timbre'])
    print(json.dumps(dict(result=report['result'],rows=[dict(seconds=r['source_seconds'],
        cost_reduction_percent=100*r['fits'][0]['cost_reduction_fraction'],main_bounds=r['fits'][0]['affine_fit']['at_bound'][:3],
        slope_bounds=r['fits'][0]['affine_fit']['slope_at_bound']) for r in rows])),flush=True)
except Exception as exc:report.update(result='failed',error=repr(exc));raise
finally:(args.out/'report.json').write_text(json.dumps(report,indent=2,allow_nan=False)+'\n',encoding='utf-8',newline='\n')
