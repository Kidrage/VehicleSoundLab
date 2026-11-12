"""Audit the exact accepted and rejected files before changing their synthesis."""
import argparse, hashlib, json, shutil, sys, urllib.request
from pathlib import Path

p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--workspace',type=Path,required=True)
p.add_argument('--out',type=Path,required=True)
a=p.parse_args();repo=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(a.workspace/'tools/python_deps'))
import numpy as np
import soundfile as sf
from phase_texture_v1.source import motion

def sha(p):
    with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
a.out.mkdir(parents=True,exist_ok=False)
old=a.workspace/'baselines/phase_texture_v1/evidence/trial2'
native=a.workspace/'references/analysis/phase_texture_c_v1/review1'
paths=[old/'accepted_original.wav',old/'common_phase_0.5.wav',native/'native_light.wav']
signals=[sf.read(path,dtype='float64',always_2d=True)[0] for path in paths]
assert all(x.shape==signals[0].shape for x in signals)
def delta(x,y):
    d=x-y
    return dict(peak_FS=float(abs(d).max()),RMS_FS=float(np.sqrt(np.mean(d*d))),
                relative_RMS_dB=float(10*np.log10(np.mean(d*d)/np.mean(y*y))))
c_motion=np.fromfile(a.workspace/'references/analysis/phase_texture_c_v1/verification1/seed_8121907_amount_1/motion.f64',dtype='<f8')
accepted_motion=motion(384000,8121907,2e-6)
np.savez_compressed(a.out/'motion_comparison.npz',accepted=accepted_motion,native=c_motion)
state=np.random.default_rng(8121907).bit_generator.state
r=dict(result='audited',numpy_version=np.__version__,
       input_sha256={str(x):sha(x) for x in paths},
       accepted_delta=delta(signals[1],signals[0]),native_delta=delta(signals[2],signals[0]),
       native_vs_accepted=delta(signals[2],signals[1]),
       motion_correlation=float(np.corrcoef(c_motion[24000:],accepted_motion[24000:])[0,1]),
       accepted_rng_state=state,causal_limit='Signal differences are measured; no unique perceptual cause is established')
# Pin the installed NumPy version, source files and BSD notices used to inspect
# PCG64/standard_normal. This downloads code only, no additional source media.
base=f'https://raw.githubusercontent.com/numpy/numpy/v{np.__version__}/'
for name in ('numpy/random/src/pcg64/pcg64.h','numpy/random/src/distributions/distributions.c',
             'numpy/random/src/distributions/ziggurat_constants.h','numpy/random/LICENSE.md',
             'numpy/random/src/pcg64/LICENSE.md'):
    target=a.out/'upstream'/name;target.parent.mkdir(parents=True,exist_ok=True)
    with urllib.request.urlopen(base+name,timeout=30) as response:target.write_bytes(response.read())
r['upstream']={str(x.relative_to(a.out)):dict(sha256=sha(x),bytes=x.stat().st_size) for x in (a.out/'upstream').rglob('*') if x.is_file()}
shutil.copy2(__file__,a.out/'executed_audit.py')
(a.out/'report.json').write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
print(json.dumps(r,ensure_ascii=False))
