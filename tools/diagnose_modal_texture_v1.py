"""Known-only local-model/persistence diagnosis and amplitude-statistics qualification."""
import argparse,json,shutil,sys
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--workspace',type=Path,required=True)
p.add_argument('--out',type=Path,required=True);a=p.parse_args();repo=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(a.workspace/'tools/python_deps'))
import numpy as np
from low_chirp_v1.fit import fit
from low_chirp_v1.link import link
from modal_texture_v1.controls import run
from research_archive_v1 import load,save,sha

a.out.mkdir(parents=True,exist_ok=False);r=dict(result='running',sources={},real_source_read=False)
try:
    files=[Path(__file__),repo/'research/modal_texture_v1_plan.json',repo/'research/low_chirp_v1_plan.json',
        repo/'tools/research_archive_v1.py',repo/'tools/idle_modal_v1/modal.py',repo/'tools/sustain_osc_v1/oracle.py',
        *sorted((repo/'tools/modal_texture_v1').glob('*.py')),
        repo/'tools/low_chirp_v1/fit.py',repo/'tools/low_chirp_v1/link.py',
        repo/'tools/line_motion_v1/local_chirps.py',repo/'tools/line_motion_v1/peaks.py',
        repo/'tools/line_motion_v1/center.py',repo/'tools/line_motion_v1/moments.py',repo/'tools/line_motion_v1/__init__.py']
    for path in files:
        name=path.relative_to(repo);dest=a.out/'exact_sources'/name;dest.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(path,dest);r['sources'][name.as_posix()]=sha(path)
    plan=load(repo/'research/modal_texture_v1_plan.json');old=load(repo/'research/low_chirp_v1_plan.json')
    controls,fixtures=run(plan);r['controls']=controls
    np.savez_compressed(a.out/'known_amplitudes.npz',**fixtures);save(a.out/'controls.json',controls)
    print(json.dumps(dict(stage='amplitude_controls',**controls)),flush=True)
    time=np.arange(144000)/48000;angle=2*np.pi*75.31*time+.4
    cases=dict(constant=.2*np.cos(angle),
        AM=.2*(1+.2*np.sin(2*np.pi*.8*time))*np.cos(angle),
        FM=.2*np.cos(angle-(1.2/1.6)*np.cos(2*np.pi*1.6*time)))
    diagnostics=[]
    for name,left in cases.items():
        audio=np.column_stack((left,.67*left));out=a.out/name;out.mkdir();windows=[];exact=[]
        for i,start in enumerate(range(0,len(audio)-old['frames']+1,old['hop'])):
            observed,state=fit(audio[start:start+old['frames']],48000,old)
            np.savez_compressed(out/f'window{i}.npz',**state)
            observed.update(window=i,start_frame=start);windows.append(observed)
            center=(start+old['frames']/2)/48000
            ff=75.31+(1.2*np.sin(2*np.pi*1.6*center) if name=='FM' else 0.)
            qq=1.2*2*np.pi*1.6*np.cos(2*np.pi*1.6*center) if name=='FM' else 0.
            exact.append(dict(lines=[dict(frequency_hz=float(ff),chirp_hz_per_second=float(qq),eligible=True)]))
        fitted=link(windows,old);truth=link(exact,old)
        save(out/'windows.json',windows);save(out/'fitted_links.json',fitted);save(out/'truth_links.json',truth)
        np.savez_compressed(out/'audio.npz',audio=audio)
        row=dict(id=name,windows=len(windows),successful=sum(w['success'] for w in windows),
            eligible=sum(x['eligible'] for w in windows for x in w['lines']),
            longest_fitted_track=max((len(x['windows']) for x in fitted['tracks']),default=0),
            longest_exact_tangent_track=max(len(x['windows']) for x in truth['tracks']))
        diagnostics.append(row);print(json.dumps(dict(stage='local_model_diagnosis',**row)),flush=True)
    assert diagnostics[0]['longest_fitted_track']==diagnostics[0]['longest_exact_tangent_track']==11
    r.update(result='known_local_model_limits_and_amplitude_proxy_checked',diagnostics=diagnostics,
        controls_passed=True,truth_used_for_fitter_initialization=False,
        real_source_read=False,old_settings_changed=False,
        note='Exact f/q tests only the old tangent-link operator; AM/FM proxy controls do not identify physical mechanical modulation.')
except Exception as exc:r.update(result='failed',error=repr(exc));raise
finally:save(a.out/'report.json',r)
print(json.dumps(dict(result=r['result'],diagnostics=r.get('diagnostics'))),flush=True)
