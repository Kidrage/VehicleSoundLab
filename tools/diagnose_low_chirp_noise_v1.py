"""A same-noise stereo counterexample for the unchanged local-chirp support rule."""
import argparse,json,shutil,sys
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--workspace',type=Path,required=True)
p.add_argument('--input',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
a=p.parse_args();repo=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(a.workspace/'tools/python_deps'))
import numpy as np
from low_chirp_v1.fit import fit
from research_archive_v1 import load,save,sha
a.out.mkdir(parents=True,exist_ok=False);r=dict(result='running',sources={},real_source_read=False)
try:
    for path in [Path(__file__),repo/'research/low_chirp_noise_v1_plan.json',
        repo/'research/low_chirp_v1_plan.json',repo/'tools/low_chirp_v1/fit.py',
        repo/'tools/line_motion_v1/local_chirps.py']:
        name=path.relative_to(repo);dest=a.out/'exact_sources'/name;dest.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(path,dest);r['sources'][name.as_posix()]=sha(path)
    parent=load(a.input/'report.json');plan=load(a.input/'exact_sources/research/low_chirp_v1_plan.json')
    assert sha(repo/'tools/low_chirp_v1/fit.py')==parent['sources']['tools/low_chirp_v1/fit.py']
    original=np.load(a.input/'known_signals.npz')['noise_audio']
    audio=np.column_stack((original[:,0],.67*original[:,0]))
    observed,state=fit(audio,48000,plan)
    np.savez_compressed(a.out/'mono_noise.npz',audio=audio,**state)
    eligible=sum(row['eligible'] for row in observed['lines'])
    old=next(row for row in parent['controls']['cases'] if row['id']=='noise')['observation']
    r.update(result='unchanged_rule_checked_on_mono_noise',original_independent_stereo_eligible=sum(x['eligible'] for x in old['lines']),
        mono_eligible=eligible,observation=observed,
        conditional_support_is_not_a_source_detector=True,
        arrays_sha256=sha(a.out/'mono_noise.npz'),parent_sha256=sha(a.input/'report.json'),
        conclusion='Even a zero result covers only this one fixture. Any nonzero result rules out interpreting conditional support as tonal-versus-noise source detection.')
except Exception as exc:r.update(result='failed',error=repr(exc));raise
finally:save(a.out/'report.json',r)
print(json.dumps({key:value for key,value in r.items() if key not in ('sources','observation')}),flush=True)
