"""Original9windows under one declared fractional-rate law, plus conditional sideband observation."""
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
from line_motion_v1.rate_coordinate_controls import controls
from line_motion_v1.rate_coordinates import fit_channel
from line_motion_v1.local_chirps import evaluate
from line_motion_v1.sideband_subspaces import observe as observe_spaces


def load(path):return json.loads(path.read_text(encoding='utf-8'))


args.out.mkdir(parents=True,exist_ok=False)
report=dict(schema='vsl.F2-rate-coordinates/1',result='running',sources={},real_audio_read=False,
    shared_phase_clock_fit=False,model_exported=False,runtime_changed=False)
try:
    for path in (Path(__file__),repo/'research/F2_rate_coordinates_v1_plan.json',repo/'references/segments_v1.json',
        repo/'tools/drive_evidence_v1/sources.py',*sorted((repo/'tools/line_motion_v1').glob('*.py'))):
        relative=path.relative_to(repo);target=args.out/'exact_sources'/relative;target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(path,target);report['sources'][relative.as_posix()]=sha(path)
    checked=controls();report['controls']=checked;assert checked['passed'],'Known rate-coordinate controls failed; no recording read'
    root=args.workspace/'references/analysis/F2_sideband_v1';parent_path=root/'observe1/report.json';parent=load(parent_path)
    old_spaces_path=root/'subspaces1/report.json';old_spaces=load(old_spaces_path)
    assert old_spaces['parent_report_sha256']==sha(parent_path)
    audio,provenance=read(args.workspace,'F2_tailpipe','fixed_window_spectral_observation');report['real_audio_read']=True
    assert provenance==parent['provenance']
    t=np.arange(48000)/48000-.5;rows=[];saved={key:[] for key in ('old','new','base','amplitude','quadrature','joint')}
    for i,row in enumerate(parent['observations']):
        start=round((row['source_seconds'][0]-6)*48000);part=audio[start:start+48000];channels=[];waves={k:[] for k in saved}
        for ch,item in enumerate(row['fits']):
            old=item['parent_fit'];nominal=np.array(old['nominal_Hz']);previous=np.array(old['fitted_parameters']);m=len(nominal)
            parameters,fit=fit_channel(part[:,ch],48000,nominal)
            central=parameters[2*m:3*m]-1j*parameters[3*m:4*m]
            observed,fits=observe_spaces(part[:,ch],nominal+parameters[:m],parameters[m:2*m],central,t)
            channels.append(dict(channel=ch,old_fit=old,new_fit=fit,subspaces=fits,
                old_subspace_summary={k:old_spaces['observations'][i]['channels'][ch][k] for k in ('amplitude_reduction_percent','quadrature_reduction_percent','joint_reduction_percent')},
                local_cost_reduction_percent=100*(1-fit['cost']/old['cost']),
                amplitude_reduction_percent=100*(1-fits['amplitude']['cost']/fits['base']['cost']),
                quadrature_reduction_percent=100*(1-fits['quadrature']['cost']/fits['base']['cost']),
                joint_reduction_percent=100*(1-fits['joint']['cost']/fits['base']['cost'])))
            waves['old'].append(evaluate(previous,nominal,t)[0]);waves['new'].append(evaluate(parameters,nominal,t)[0])
            for key in observed:waves[key].append(observed[key])
        rows.append(dict(source_seconds=row['source_seconds'],channels=channels))
        for key in saved:saved[key].append(np.column_stack(waves[key]))
    np.savez_compressed(args.out/'observations.npz',audio=audio,**{k:np.stack(v) for k,v in saved.items()})
    report.update(result='all9_fractional_rate_local_coordinates_observed_not_shared_phase_DNA',
        provenance=provenance,parent_report_sha256=sha(parent_path),old_subspaces_report_sha256=sha(old_spaces_path),
        observations=rows,arrays_sha256=sha(args.out/'observations.npz'),phase_extracted_real_model_permitted=False,RPM_inferred=False,
        limits=['New relative-rate vector changes the local engineering prior; lower and higher lines can be respectively narrower and wider',
            'Independent local phases are not a recovered common engine clock or measured RPM',
            'Conditional sideband changes can follow coordinate changes; not identified mechanical modulation or improved timbre',
            'All failures, boundary flags and increased costs remain explicit'])
    print(json.dumps(dict(result=report['result'],rows=[dict(seconds=r['source_seconds'],cost_change_percent=r['channels'][0]['local_cost_reduction_percent'],
        bounds=r['channels'][0]['new_fit']['at_bound'],success=r['channels'][0]['new_fit']['success'],
        Q_before=r['channels'][0]['old_subspace_summary']['quadrature_reduction_percent'],Q_after=r['channels'][0]['quadrature_reduction_percent']) for r in rows])),flush=True)
except Exception as exc:report.update(result='failed',error=repr(exc));raise
finally:(args.out/'report.json').write_text(json.dumps(report,indent=2,allow_nan=False)+'\n',encoding='utf-8',newline='\n')
