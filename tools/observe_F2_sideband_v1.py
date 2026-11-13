"""Conditional fixed3Hz sideband observations of all9 frozen F2 local windows."""
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
from line_motion_v1.sideband_controls import controls
from line_motion_v1.sidebands import observe
from line_motion_v1.local_chirps import evaluate


def load(path):return json.loads(path.read_text(encoding='utf-8'))


args.out.mkdir(parents=True,exist_ok=False)
report=dict(schema='vsl.F2-sidebands/1',result='running',sources={},real_audio_read=False,
    shared_phase_clock_fit=False,nonlinear_fit_run=False,model_exported=False,runtime_changed=False)
try:
    for path in (Path(__file__),repo/'research/F2_sideband_v1_plan.json',repo/'references/segments_v1.json',
        repo/'tools/drive_evidence_v1/sources.py',*sorted((repo/'tools/line_motion_v1').glob('*.py'))):
        relative=path.relative_to(repo);target=args.out/'exact_sources'/relative;target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(path,target);report['sources'][relative.as_posix()]=sha(path)
    checked=controls();report['controls']=checked
    assert checked['passed'],'Conditional sideband operator controls failed; no recording read'
    base=args.workspace/'references/analysis';prior_path=base/'F2_local_chirps_v1/observe1/report.json';prior=load(prior_path)
    counter_path=base/'F2_peak_identity_v1/observe1/report.json';counter=load(counter_path)
    assert counter['prior_report_sha256']==sha(prior_path)
    audio,provenance=read(args.workspace,'F2_tailpipe','fixed_window_spectral_observation');report['real_audio_read']=True
    t=np.arange(48000)/48000-.5;rows=[];before=[];after=[]
    for i,row in enumerate(prior['observations']):
        start=round((row['source_seconds'][0]-6)*48000);part=audio[start:start+48000]
        fits=[];old=[];new=[]
        for ch in range(2):
            constant=counter['counterfactual'][ch]['fit'] if i==1 else row['measured']['local_chirp_fit'][ch]
            parameters=np.array(constant['fitted_parameters']);nominal=np.array(constant['nominal_Hz']);m=len(nominal)
            frequency=nominal+parameters[:m];chirp=parameters[m:2*m]
            fitted,measurement=observe(part[:,ch],frequency,chirp,t)
            fits.append(dict(channel=ch,parent_fit=constant,measurement=measurement,
                cost_reduction_fraction=1-measurement['cost']/constant['cost'],
                interpretation='Conditional waveform coefficients only; parent phase unqualified; no physical AM/FM source inference'))
            old.append(evaluate(parameters,nominal,t)[0]);new.append(fitted)
        rows.append(dict(source_seconds=row['source_seconds'],fits=fits));before.append(np.column_stack(old));after.append(np.column_stack(new))
    np.savez_compressed(args.out/'observations.npz',audio=audio,before=np.stack(before),after=np.stack(after))
    report.update(result='all9_fixed3Hz_sideband_parities_observed_CONDITIONAL_not_engine_source_classification',
        provenance=provenance,prior_report_sha256=sha(prior_path),counterfactual_report_sha256=sha(counter_path),
        observations=rows,arrays_sha256=sha(args.out/'observations.npz'),phase_extracted_real_model_permitted=False,RPM_inferred=False,
        limits=['Input local phase coordinates remain unqualified and retain all original boundary flags',
            'Every sideband pair admits AM/quadrature algebra; independent tones can be exactly equivalent',
            'Fixed3Hz describes one predeclared projection, not all modulation rates or total engine detail',
            'Training reduction with additional coefficients does not prove physical source recovery or improved timbre'])
    print(json.dumps(dict(result=report['result'],rows=[dict(seconds=r['source_seconds'],cost_reduction_percent=100*r['fits'][0]['cost_reduction_fraction'],
        condition=r['fits'][0]['measurement']['condition']) for r in rows])),flush=True)
except Exception as exc:report.update(result='failed',error=repr(exc));raise
finally:(args.out/'report.json').write_text(json.dumps(report,indent=2,allow_nan=False)+'\n',encoding='utf-8',newline='\n')
