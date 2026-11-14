"""Bind the independently solved powers to the exact gains the renderer consumes."""
import argparse,shutil,sys
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__)
for key in ['workspace','model','audit','out']:p.add_argument('--'+key,type=Path,required=True)
a=p.parse_args();sys.path.insert(0,str(a.workspace/'tools/python_deps'))
import numpy as np
from research_archive_v1 import load,save,sha

a.out.mkdir(parents=True,exist_ok=False);shutil.copy2(__file__,a.out/'executed_verifier.py')
r=dict(result='running',model_sha256=sha(a.model/'model.json'),audio_audit_sha256=sha(a.audit/'report.json'))
try:
    compilation=load(a.model/'report.json');model=load(a.model/'model.json');audio=load(a.audit/'report.json')
    assert compilation['model_sha256']==r['model_sha256'] and audio['result']=='passed'
    assert audio['compile_sha256']==sha(a.model/'report.json')
    train=next(x for x in compilation['assessment'] if x['part']=='train')
    A=np.array(train['lower_unit_power_matrix'])[[2,3]]
    target=np.array(train['target_residual_power_LR'])[[2,3]]-np.array(train['fixed_upper_power_LR'])[[2,3]]
    squared=np.linalg.solve(A,target)
    actual=np.array([[k['gain']**2,(k['gain']*k['right_over_left'])**2] for k in model['kernels']])
    error=float(abs(squared-actual).max());assert error<1e-12 and np.all(actual>0)
    assert np.isfinite(np.array(model['main_amplitude_LR'])).all() and np.all(np.array(model['main_amplitude_LR'])>0)
    assert np.isfinite(np.array([k['taps'] for k in model['kernels']])).all()
    assert model['recorded_trajectory'] is False and model['source_main_residual_cross_not_modeled'] is True
    r.update(result='passed',actual_rendered_gain_squared_binding_error=error,
             both_channels_bound=True,profile_contains_only_parameters=True,runtime_changed=False)
except Exception as exc:r.update(result='failed',error=repr(exc));raise
finally:save(a.out/'report.json',r)
print(r,flush=True)
