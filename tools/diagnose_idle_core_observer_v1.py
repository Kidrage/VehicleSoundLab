"""Isolate main/detail and actual/known synthesis phasors; no renderer modification."""
import argparse,shutil,sys
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__)
for key in ['workspace','input','out']:p.add_argument('--'+key,type=Path,required=True)
a=p.parse_args();sys.path.insert(0,str(a.workspace/'tools/python_deps'))
import numpy as np
import soundfile as sf
from research_archive_v1 import load,save,sha
from idle_phase_amplitude_v1.observe import observe,statistics
from idle_conditioned_detail_v1.features import phases
from idle_phase_recipe_v1.phase import spline,phasors

a.out.mkdir(parents=True,exist_ok=False);shutil.copy2(__file__,a.out/'executed_diagnostic.py')
r=dict(result='running',input_sha256=sha(a.input/'report.json'),cases=[])
try:
    parent=a.workspace/'baselines';phase_root=parent/'idle_phase_recipe_v1/evidence/render2'
    model=load(phase_root/'model.json');profile=load(parent/'fixed_source_profiles_v1/evidence/trial1/F2_tailpipe/profile.json')
    freq=np.array(profile['modal']['frequencies_hz']);rows=load(a.input/'report.json')['renders']
    for row in rows:
        seed=row['seed']
        with np.load(phase_root/f'motion_{seed}.npz') as f:motion=spline(model,f['coordinate_nodes'])
        z=phasors(model,motion,np.arange(144000)/48000)
        for amount in ['0.0','1.0']:
            main,_=sf.read(a.input/row['files']['main_'+amount]['file'],frames=144000,always_2d=True)
            mix,_=sf.read(a.input/row['files']['mix_'+amount]['file'],frames=144000,always_2d=True)
            for bus,audio in [('main',main),('mix',mix)]:
                for mode,phase in [('known_generated',z),('measured_acoustic',phases(audio[:,0],freq[[1,2,4]]))]:
                    observation=observe(audio,freq,phase);summary,x=statistics(observation['coefficients'])
                    r['cases'].append(dict(seed=seed,amount=amount,bus=bus,phase_basis=mode,statistics=summary))
                    print(dict(seed=seed,amount=amount,bus=bus,mode=mode,std=summary['raw_log_std']),flush=True)
    r.update(result='isolated_core_observer_diagnostic_complete',new_model=False,runtime_changed=False,
             limitation='Known synthesis phasors are a diagnostic only, unavailable as physical ground truth in recordings.')
except Exception as exc:r.update(result='failed',error=repr(exc));raise
finally:save(a.out/'report.json',r)
