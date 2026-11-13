"""Compare same-dimensional amplitude/quadrature spaces on fixed observed coordinates."""
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
from line_motion_v1.sideband_subspaces import observe
from line_motion_v1.sideband_subspace_controls import controls


args.out.mkdir(parents=True,exist_ok=False)
report=dict(schema='vsl.F2-sideband-subspaces/1',result='running',sources={},real_audio_read=False,
    nonlinear_fit_run=False,shared_phase_clock_fit=False,model_exported=False,runtime_changed=False)
try:
    root=args.workspace/'references/analysis/F2_sideband_v1';parent_path=root/'observe1/report.json'
    parent=json.loads(parent_path.read_text(encoding='utf-8'));arrays=np.load(root/'observe1/observations.npz')
    assert sha(root/'observe1/observations.npz')==parent['arrays_sha256']
    for path in (Path(__file__),repo/'research/F2_sideband_subspaces_v1_plan.json',repo/'tools/drive_evidence_v1/sources.py',
        *sorted((repo/'tools/line_motion_v1').glob('sideband*.py'))):
        relative=path.relative_to(repo);target=args.out/'exact_sources'/relative;target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(path,target);report['sources'][relative.as_posix()]=sha(path)
    checked=controls();report['controls']=checked;assert checked['passed'],'Subspace controls failed; no real audio read'
    audio,provenance=read(args.workspace,'F2_tailpipe','fixed_window_spectral_observation');report['real_audio_read']=True
    assert provenance==parent['provenance'] and np.array_equal(audio,arrays['audio'])
    t=np.arange(48000)/48000-.5;observations=[];saved={k:[] for k in ('base','amplitude','quadrature','joint')}
    for i,row in enumerate(parent['observations']):
        start=round((row['source_seconds'][0]-6)*48000);part=audio[start:start+48000];channels=[];w={k:[] for k in saved}
        for ch,item in enumerate(row['fits']):
            fit=item['parent_fit'];p0=np.array(fit['fitted_parameters']);nominal=np.array(fit['nominal_Hz']);m=len(nominal)
            central=p0[2*m:3*m]-1j*p0[3*m:4*m]
            waves,fits=observe(part[:,ch],nominal+p0[:m],p0[m:2*m],central,t)
            error=float(abs(waves['joint']-arrays['after'][i,:,ch]).max());assert error<=1e-10
            channels.append(dict(channel=ch,models=fits,joint_vs_full_wave_error=error,parent_main_at_bound=fit['at_bound'][:3],
                amplitude_reduction_percent=100*(1-fits['amplitude']['cost']/fits['base']['cost']),
                quadrature_reduction_percent=100*(1-fits['quadrature']['cost']/fits['base']['cost']),
                joint_reduction_percent=100*(1-fits['joint']['cost']/fits['base']['cost'])))
            for key in saved:w[key].append(waves[key])
        observations.append(dict(source_seconds=row['source_seconds'],channels=channels))
        for key in saved:saved[key].append(np.column_stack(w[key]))
    np.savez_compressed(args.out/'subspaces.npz',**{k:np.stack(v) for k,v in saved.items()})
    report.update(result='all9_equal_dimension_A_Q_conditional_subspaces_observed_not_mechanical_source_classification',
        parent_report_sha256=sha(parent_path),provenance=provenance,observations=observations,arrays_sha256=sha(args.out/'subspaces.npz'),
        limits=['A-only and Q-only each add2m parameters; their finite-window spaces need not be orthogonal',
            'Static coordinate rotation is invariant; wrong frequency/phase trajectories can still create apparent quadrature detail',
            'Training-cost comparisons on unqualified old coordinates do not identify physical AM/FM or mechanical sources'])
    print(json.dumps(dict(result=report['result'],rows=[dict(seconds=r['source_seconds'],A=r['channels'][0]['amplitude_reduction_percent'],
        Q=r['channels'][0]['quadrature_reduction_percent'],joint=r['channels'][0]['joint_reduction_percent']) for r in observations])),flush=True)
except Exception as exc:report.update(result='failed',error=repr(exc));raise
finally:(args.out/'report.json').write_text(json.dumps(report,indent=2,allow_nan=False)+'\n',encoding='utf-8',newline='\n')
