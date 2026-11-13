"""Native low-band moving/fixed local observations on unchanged training samples."""
import argparse,json,shutil,sys
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--workspace',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
a=p.parse_args();repo=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(a.workspace/'tools/python_deps'))
import numpy as np
import soundfile as sf
from low_chirp_v1 import controls,fit,link
from research_archive_v1 import load,save,sha


a.out.mkdir(parents=True,exist_ok=False)
report=dict(schema='vsl.low-chirp-observation/1',result='running',sources={},real_source_read=False,
    holdout_read=False,shared_phase_fit=False,model_exported=False,runtime_changed=False)
try:
    plan=load(repo/'research/low_chirp_v1_plan.json')
    files=[Path(__file__),repo/'research/low_chirp_v1_plan.json',repo/'tools/research_archive_v1.py',
        repo/'tools/line_motion_v1/local_chirps.py',repo/'tools/line_motion_v1/peaks.py',
        repo/'tools/line_motion_v1/center.py',*sorted((repo/'tools/low_chirp_v1').glob('*.py'))]
    for path in files:
        name=path.relative_to(repo);dest=a.out/'exact_sources'/name;dest.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(path,dest);report['sources'][name.as_posix()]=sha(path)
    def progress(row):print(json.dumps(row),flush=True)
    checked,fixtures=controls.run(plan,progress)
    report['controls']=checked;np.savez_compressed(a.out/'known_signals.npz',**fixtures)
    save(a.out/'controls.json',checked)
    assert checked['passed']
    parent=a.workspace/'references/analysis/fixed_source_profiles_v1/trial1'
    frozen=a.workspace/'baselines/fixed_source_profiles_v1/evidence/trial1'
    sources=[]
    for spec in plan['real_sources']:
        name=spec['id'];path=parent/name/'training.wav'
        assert sha(path)==sha(frozen/name/'training.wav')
        audio,rate=sf.read(path,always_2d=True);report['real_source_read']=True
        assert rate==48000 and len(audio)==round((spec['seconds'][1]-spec['seconds'][0])*rate)
        out=a.out/name;out.mkdir();windows=[]
        for number,start in enumerate(range(0,len(audio)-plan['frames']+1,plan['hop'])):
            observed,state=fit.fit(audio[start:start+plan['frames']],rate,plan)
            observed.update(window=number,start_frame=start,source_center_seconds=spec['seconds'][0]+(start+plan['frames']/2)/rate)
            np.savez_compressed(out/f'window{number}.npz',**state)
            windows.append(observed)
            progress(dict(source=name,window=number,candidates=len(observed['lines']),
                eligible=sum(r['eligible'] for r in observed['lines']),success=observed['success']))
        correspondence=link.link(windows,plan)
        save(out/'windows.json',windows);save(out/'correspondence.json',correspondence)
        sources.append(dict(id=name,training_seconds=spec['seconds'],input_sha256=sha(path),
            windows=len(windows),candidates=sum(len(w['lines']) for w in windows),
            eligible=sum(r['eligible'] for w in windows for r in w['lines']),
            successful_windows=sum(w['success'] for w in windows),
            moving_tracks=sum(r['classification']=='locally_moving' for r in correspondence['tracks']),
            stationary_tracks=sum(r['classification']=='locally_stationary' for r in correspondence['tracks']),
            unresolved_tracks=sum(r['classification']=='unresolved' for r in correspondence['tracks'])))
    report.update(result='native_independent_low_chirps_and_conservative_tracks_observed',observations=sources,
        limitations=['Independent local chirps are not a common engine phase or physical sound-source decomposition.',
            'Overlapping training windows are not independent validation; local support can be model-confounded.',
            'A low-rev is not confirmed warm idle. F2 exact RPM, warm state and stock exhaust unknown.',
            'No synthesized audio, phase-warp, new profile, C, UI or driving mapping was produced.'])
except Exception as exc:
    report.update(result='failed',error=repr(exc));raise
finally:save(a.out/'report.json',report)
print(json.dumps(dict(result=report['result'],observations=report.get('observations'))),flush=True)
