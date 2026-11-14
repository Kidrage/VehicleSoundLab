"""Posthoc source-only clue for the next idle-core observation, not a new AM recipe."""
import argparse,math,shutil,sys
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__)
for key in ['workspace','out']:p.add_argument('--'+key,type=Path,required=True)
a=p.parse_args();sys.path.insert(0,str(a.workspace/'tools/python_deps'))
import numpy as np
from research_archive_v1 import load,save,sha

a.out.mkdir(parents=True,exist_ok=False);shutil.copy2(__file__,a.out/'executed_inspector.py')
parent=a.workspace/'baselines/modal_texture_v1/evidence/trial1'
path=parent/'source_observations.npz'
with np.load(path) as f:values=f['centered_log_magnitude'][:,[1,2,4]]
assert values.shape==(141,3)
covariance=values.T@values/len(values)
lag=10
numerator=math.fsum(float(v*w) for v,w in zip(values[:-lag].ravel(),values[lag:].ravel()))
denominator=math.fsum(float(v*v) for v in values[:-lag].ravel())
alpha=numerator/denominator
check=sum(float(np.dot(values[:-lag,k],values[lag:,k])) for k in range(3))/float(np.sum(values[:-lag]**2))
assert abs(alpha-check)<1e-14
model=load(parent/'profile.json')
report=dict(schema='vsl.idle-core-amplitude-diagnostic/1',result='source_followup_clue_NOT_synthesis_profile',
    input=str(path),input_sha256=sha(path),model_input_sha256=sha(parent/'profile.json'),
    selected_indices=[1,2,4],selected_frequencies_hz=[model['modal']['frequencies_hz'][j] for j in [1,2,4]],
    raw_uncapped_log_std=np.sqrt(np.diag(covariance)).tolist(),raw_uncapped_covariance=covariance.tolist(),
    observation_frames=9600,observation_hop=960,lag_frames=9600,raw_uncapped_trace_correlation=alpha,
    recorded_amplitude_trajectory_exported=False,check_used=False,new_audio_generated=False,runtime_changed=False,
    limits='Posthoc reuse of old fixed-frequency weighted-projection TRAIN magnitudes; FM and window leakage confound apparent AM. Not physical combustion AM, an identified time law or a reason to transplant into the new phase model.',
    next='Observe main amplitudes using the actual low acoustic phasors, with known no-AM nonlinear-FM and AM controls; check another source portion before designing a fresh correlated generator. Do not clip this negative correlation to zero or copy the old measured amplitude trajectory.')
save(a.out/'report.json',report)
print(dict(result=report['result'],raw_log_std=report['raw_uncapped_log_std'],raw_200ms_correlation=alpha))
