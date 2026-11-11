"""Check actual C energy, complex stereo covariance, pitch and source preservation."""
import argparse
import json
from pathlib import Path
import subprocess
import sys
import time

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--workspace',type=Path,required=True)
parser.add_argument('--probe',type=Path,required=True)
parser.add_argument('--fitted',type=Path,required=True)
parser.add_argument('--out',type=Path,required=True)
args=parser.parse_args()
sys.path.insert(0,str(args.workspace/'tools/python_deps'))
import numpy as np
import soundfile as sf
from scipy import signal
from drive_evidence_v1.sources import sha
from residual_osc_v1.fit import export
from residual_osc_v1.spectrum import matrices,error

repo=Path(__file__).resolve().parents[1]
args.out.mkdir(parents=True,exist_ok=False)
build=json.loads((args.fitted/'report.json').read_text(encoding='utf-8'))
assert sha(args.probe)==build['probe_sha256']
for name,expected in build['source_sha256'].items():assert sha(repo/name)==expected,name
fixtures={
    'stereo':[dict(hz=[1200,2400],power=[.003,.001],coherence=[-.6,.2]),
              dict(hz=[2400,4000],power=[.001,.004],coherence=[0,0]),
              dict(hz=[4000,8000],power=[.002,.002],coherence=[0,.8])],
    'mono':[dict(hz=[1200,8000],power=[.006,.006],coherence=[1,0])]}
evidence={}
for name,rows in fixtures.items():
    profile=args.out/(name+'.residual');export(profile,rows)
    results=[]
    for seed in (101,202,303):
        target=args.out/f'{name}_{seed}.wav'
        command=[str(args.probe),str(profile),str(target),'12','1','1',str(seed)]
        started=time.perf_counter();subprocess.run(command,check=True,capture_output=True,timeout=90)
        wall=time.perf_counter()-started
        audio,rate=sf.read(target,always_2d=True)
        assert rate==48000 and audio.shape==(576000,2) and np.isfinite(audio).all()
        desired=[dict(hz=r['hz'],power=r['power'],cross=[v*np.sqrt(np.prod(r['power'])) for v in r['coherence']]) for r in rows]
        deviations=error(desired,matrices(audio, [r['hz'] for r in rows]))
        assert max(abs(v) for r in deviations for v in r['power_delta_db'])<.5
        assert max(r['complex_coherence_error'] for r in deviations)<.04
        if name=='mono':assert np.array_equal(audio[:,0],audio[:,1])
        assert not np.array_equal(audio[:288000],audio[288000:])
        results.append(dict(seed=seed,sha256=sha(target),wall_seconds=wall,errors=deviations))
    assert len({r['sha256'] for r in results})==3
    evidence[name]=results

# Same deterministic cloud, frequency and duration scale correctly without
# changing playback length. Compare spectra on the known band at bounded pitch.
rows=fixtures['mono'];pitch_evidence=[]
for pitch in (.9,1.1):
    path=args.out/f'pitch_{pitch:.1f}.wav'
    command=[str(args.probe),str(args.out/'mono.residual'),str(path),'8',str(pitch),'1','101']
    subprocess.run(command,check=True,capture_output=True,timeout=90)
    audio,rate=sf.read(path,always_2d=True)
    assert rate==48000 and audio.shape==(384000,2)
    hz,p=signal.welch(audio,fs=48000,nperseg=16384,axis=0,detrend=False)
    supported=(hz>=1200*pitch-25)&(hz<=8000*pitch+25)
    fraction=float(p[supported].sum()/p.sum())
    assert fraction>.999
    pitch_evidence.append(dict(pitch=pitch,sha256=sha(path),power_inside_carrier_bounds=fraction))

real={}
for name,case in build['cases'].items():
    out=args.fitted/name
    assert sha(out/'voice.residual')==case['profile_sha256']
    for render in case['renders']:
        pitch=render['pitch']
        residual,_=sf.read(out/f'residual_{pitch:.1f}.wav',always_2d=True)
        base,_=sf.read(out/f'base_{pitch:.1f}.wav',always_2d=True)
        mixed,_=sf.read(out/f'mix_{pitch:.1f}.wav',always_2d=True)
        expected=(base+residual).astype(np.float32).astype(np.float64)
        assert np.array_equal(mixed,expected)
        original,_=sf.read(render['base_source'],always_2d=True)
        assert np.array_equal(base,original)
        assert sha(out/f'residual_{pitch:.1f}.wav')==render['residual_sha256']
        assert sha(out/f'mix_{pitch:.1f}.wav')==render['mixed_sha256']
    peak_error=max(abs(v) for row in case['residual_target_error'] for v in row['power_delta_db'])
    mix_error=max(abs(v) for row in case['after_error'] for v in row['power_delta_db'])
    assert peak_error<.6 and mix_error<.5
    real[name]=dict(max_residual_target_db_error=peak_error,max_mix_training_band_error_db=mix_error,
        max_mix_training_coherence_error=max(r['complex_coherence_error'] for r in case['after_error']),
        base_float_equal=True,mixture_float_equal=True,
        warning='Same recording/seed used in fit; no held-out naturalness claim')
result=dict(schema='vsl.residual-osc-verification/1',result='pass',human_accepted=False,driving_attached=False,
    build_sha256=sha(args.fitted/'report.json'),probe_sha256=sha(args.probe),fixtures=evidence,pitch=pitch_evidence,real=real,
    source_sha256={p.relative_to(repo).as_posix():sha(p) for p in
        [Path(__file__),*repo.joinpath('modules/sound_residual').glob('*.[ch]'),
         *repo.joinpath('experiments/residual_osc_v1').glob('*.c'),*repo.joinpath('tools/residual_osc_v1').glob('*.py')]})
(args.out/'verification.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
print(json.dumps(dict(result='pass',fixtures=len(evidence),known_seeds=3,real=real)))
