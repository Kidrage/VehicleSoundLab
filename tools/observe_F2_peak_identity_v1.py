"""Track all saved candidates and refit one predeclared omitted-peak counterfactual."""
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
from line_motion_v1.correspondence import correspond
from line_motion_v1.identity_controls import controls
from line_motion_v1.local_chirps import fit_channel,evaluate

def load(path):return json.loads(path.read_text(encoding='utf-8'))

args.out.mkdir(parents=True,exist_ok=False)
report=dict(schema='vsl.F2-peak-identity/1',result='running',sources={},real_audio_read=False,
    shared_phase_clock_fit=False,model_exported=False,runtime_changed=False)
try:
    prior_path=args.workspace/'references/analysis/F2_local_chirps_v1/observe1/report.json';prior=load(prior_path)
    for path in (Path(__file__),repo/'research/F2_peak_identity_v1_plan.json',repo/'tools/drive_evidence_v1/sources.py',
        repo/'references/segments_v1.json',*sorted((repo/'tools/line_motion_v1').glob('*.py'))):
        relative=path.relative_to(repo);target=args.out/'exact_sources'/relative
        target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(path,target);report['sources'][relative.as_posix()]=sha(path)
    checked=controls();report['controls']=checked
    assert checked['passed'],'Known controls failed; no recording read'
    channels=[]
    for ch in range(2):
        frames=[]
        for row in prior['observations']:
            candidates=[]
            for cell,group in enumerate(row['measured']['candidates']):
                candidates.extend(dict(frequency_Hz=p['native_bin_Hz'],power=p['power'],cell=cell,rank=rank+1)
                                  for rank,p in enumerate(group[ch]))
            frames.append(candidates)
        channels.append(correspond(frames))
    target=prior['observations'][1];assert target['source_seconds']==[6.5,7.5]
    audio,provenance=read(args.workspace,'F2_tailpipe','fixed_window_spectral_observation');report['real_audio_read']=True
    part=audio[24000:72000];t=np.arange(48000)/48000-.5
    results=[];signals=[]
    for ch in range(2):
        observed=target['measured'];old=observed['local_chirp_fit'][ch]
        nominal=np.array(old['nominal_Hz']);parameters=np.array(old['fitted_parameters'])
        assert 37 not in nominal and 45 in nominal
        low=observed['candidates'][4][ch]
        assert any(p['native_bin_Hz']==37 for p in low)
        selected=np.r_[nominal,37.]
        new_parameters,fit=fit_channel(part[:,ch],48000,selected)
        before=evaluate(parameters,nominal,t)[0];after=evaluate(new_parameters,selected,t)[0]
        window=np.sin(np.pi*np.arange(48000)/48000)**2
        carrier=window*np.exp(-2j*np.pi*37*t)
        results.append(dict(channel=ch,original_nominal_Hz=nominal.tolist(),new_nominal_Hz=selected.tolist(),fit=fit,
            original_cost=old['cost'],new_cost=fit['cost'],cost_reduction_fraction=1-fit['cost']/old['cost'],
            original_at_bound=old['at_bound'],new_at_bound=fit['at_bound'],
            residual37_projection_before=float(abs(np.sum((part[:,ch]-before)*carrier))/window.sum()),
            residual37_projection_after=float(abs(np.sum((part[:,ch]-after)*carrier))/window.sum()),
            limits='Post-observation selected window and extra measured component; lower training loss alone is not source or timbre qualification'))
        signals.append(dict(before=before,after=after))
    np.savez_compressed(args.out/'counterfactual.npz',audio=part,
        before=np.column_stack([x['before'] for x in signals]),after=np.column_stack([x['after'] for x in signals]))
    report.update(result='all_peak_correspondence_and_omitted37_counterfactual_observed_not_idle_DNA',
        prior_report_sha256=sha(prior_path),provenance=provenance,
        source_windows=[r['source_seconds'] for r in prior['observations']],channels=channels,
        counterfactual_source_seconds=[6.5,7.5],counterfactual=results,
        arrays_sha256=sha(args.out/'counterfactual.npz'),phase_extracted_real_model_permitted=False,
        RPM_inferred=False,limits=['Graph tracks are discrete unambiguous local correspondences, not a physical source tracker or phase clock',
            'All ambiguous links retained; no amplitude-based choice or gap filling',
            'Actual added37Hz is a measured secondary candidate, not a generated or truth-seeded carrier',
            'Six-component local counterfactual changes neither original five-component results nor accepted voices'])
    print(json.dumps(dict(result=report['result'],counterfactual=results)),flush=True)
except Exception as exc:report.update(result='failed',error=repr(exc));raise
finally:(args.out/'report.json').write_text(json.dumps(report,indent=2,allow_nan=False)+'\n',encoding='utf-8',newline='\n')
