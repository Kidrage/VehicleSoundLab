"""New crank only: sparse moving OSC plus residual; catch/idle PCM preserved."""
import argparse,json,hashlib,shutil
from pathlib import Path
from copy import deepcopy
import numpy as np,soundfile as sf
from startup_character_v1.native import Starter
from startup_character_v1.ridge_native import RidgeStarter
from startup_character_v1.ridges import render

RATE=48000
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def save(p,x):p.write_text(json.dumps(x,ensure_ascii=False,indent=2),encoding='utf-8')

def known(library,old_library,out):
    out.mkdir();zero=[]
    for k in range(3):
        p=out/f'zero-{k}.sfir';p.write_text('VSL_SPECTRAL_TEXTURE 1 48000 1 0\n1 0 1\n0\n',encoding='ascii');zero.append(dict(path=str(p)))
    atoms=[dict(start_frame=1536,frames=4096,hz=750.,slew_hz_per_second=2000.,amplitude=[.3,.2],phase=[.2,.7]),
           dict(start_frame=6144,frames=4096,hz=1500.,slew_hz_per_second=-2000.,amplitude=[.1,.15],phase=[.1,-.3])]
    p=dict(profiles=zero,envelope=[1.]*9,variation=0.,ridges=atoms,reference_frames=12288,ridge_variation=0.,ridge_pitch=1.)
    def run(profile,frames,chunk=217,seed=32149,lib=library,kind=RidgeStarter):
        s=kind(lib,profile,seed);progress=np.arange(frames)/frames;gate=np.ones(frames,dtype=int)
        try:return np.concatenate([s.process(progress[n:n+chunk],gate[n:n+chunk]) for n in range(0,frames,chunk)])
        finally:s.close()
    a=run(p,12288);expected=render(atoms,12288)*(1-np.exp(-(np.arange(12288)+1)/384))[:,None]
    error=float(np.max(abs(a-expected)));assert error<3e-8,error
    assert np.array_equal(a,run(p,12288,479))
    # Independent analytic phase oracle for time and pitch controls.
    q=deepcopy(p);q['ridge_pitch']=1.1;frames=15360;expected=np.zeros((frames,2))
    positions=np.arange(frames)/frames*q['reference_frames']
    for r in atoms:
        local=positions-r['start_frame'];ok=(local>=0)&(local<r['frames']);t=local[ok]/RATE
        angle=2*np.pi*1.25*1.1*(r['hz']*t+.5*r['slew_hz_per_second']*t*t)
        window=.5-.5*np.cos(2*np.pi*local[ok]/r['frames'])
        expected[ok]+=window[:,None]*np.array(r['amplitude'])*np.cos(angle[:,None]+r['phase'])
    expected*= (1-np.exp(-(np.arange(frames)+1)/384))[:,None]
    changed=run(q,frames);control_error=float(np.max(abs(changed-expected)));assert control_error<3e-8,control_error
    previous=Path('E:/VehicleSoundLab/references/analysis/startup_character_v1/attempt2/model/profile.json')
    p=json.loads(previous.read_text(encoding='utf-8'))
    old=run(p,19200,lib=old_library,kind=Starter);new=run(p,19200,kind=Starter)
    assert np.array_equal(old,new)
    save(out/'verification.json',dict(known_C_oracle_error=error,independent_pitch_duration_error=control_error,partition_exact=True,old_noise_only_PCM_exact=True))

def main():
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);a=p.parse_args();a.output.mkdir(parents=True,exist_ok=False)
    repo=Path(__file__).resolve().parents[1];workspace=Path('E:/VehicleSoundLab/references/analysis')
    library=repo/'build-startup-character-v2/Release/startup_character_bridge.dll'
    old=workspace/'startup_character_v1/attempt2';known(library,old/'startup_character_bridge.dll',a.output/'known')
    author=workspace/'startup_rhythm_v1/author1';profile=json.loads((author/'profile.json').read_text(encoding='utf-8'))
    model=a.output/'model';model.mkdir()
    for row in profile['profiles']:
        src=Path(row['path']);dest=model/src.name;shutil.copy2(src,dest);row.update(path=str(dest),sha256=sha(dest))
    profile['phase']='Sparse moving-OSC initial phase parameters retained; residual source phase discarded'
    save(model/'profile.json',profile)
    states=json.loads((old/'telemetry.json').read_text(encoding='utf-8'))['candidate'];frames=192000
    gate=np.zeros(frames,dtype=int);progress=np.zeros(frames);start=None
    for state in states:
        n=state['frame']
        if state['lifecycle']==2:
            if start is None:start=n
            gate[n:n+240]=1;progress[n:n+240]=np.clip((np.arange(n,n+240)-start)/27840,0,1)
        elif start is not None:progress[n:n+240]=1
    def generate(seed,strength=1.,chunk=479):
        v=RidgeStarter(library,profile,seed)
        try:return np.concatenate([v.process(progress[n:n+chunk],gate[n:n+chunk],strength) for n in range(0,frames,chunk)])
        finally:v.close()
    previous,_=sf.read(old/'Starter-only.wav',always_2d=True);dna,_=sf.read(old/'DNA-only.wav',always_2d=True)
    calibration=generate(32149);active=slice(round(.64*RATE),round(1.15*RATE))
    gain=float(np.sqrt(np.mean(previous[active]**2)/np.mean(calibration[active].astype(float)**2)))
    assert 0<gain<4
    outputs={};results=[]
    for seed in (45943,57269):
        crank=generate(seed,gain);mix=(dna.astype('float32')+crank).astype('float32')
        assert np.isfinite(mix).all() and np.max(abs(mix))<.95
        assert np.array_equal(mix[round(1.8*RATE):],dna[round(1.8*RATE):].astype('float32'))
        name=f'Candidate-{seed}.wav';sf.write(a.output/name,mix,RATE,subtype='FLOAT')
        sf.write(a.output/f'Crank-{seed}.wav',crank,RATE,subtype='FLOAT');results.append(crank)
        outputs[name]=dict(sha256=sha(a.output/name),peak=float(np.max(abs(mix))),drag_rms_vs_previous_db=float(10*np.log10(np.mean(crank[active].astype(float)**2)/np.mean(previous[active]**2))))
    assert np.array_equal(results[0],generate(45943,gain,217))
    assert not np.array_equal(results[0],results[1])
    for source,name in [('Candidate-77317.wav','Previous-noise-only.wav'),('Reference-exterior.wav','Reference-exterior.wav'),('DNA-only.wav','DNA-only.wav')]:
        shutil.copy2(old/source,a.output/name);outputs[name]=dict(sha256=sha(a.output/name))
    save(a.output/'recipe.json',dict(profile=profile,starter_gain=gain,calibration_seed=32149,fresh_seeds=[45943,57269],calibration='One global crank RMS gain from development seed; same gain for both fresh seeds',catch_and_idle='Exact unchanged DNA PCM for this controlled audition; main system still generates this with C, no recorded vehicle PCM synthesis'))
    report=dict(schema='vsl.startup-moving-osc-review/1',status='pending_listening',previous_user_feedback='Crank resembles wind; lacks mechanical rhythm',
       starter_native_sha256=sha(library),source_hash=profile['source_sha256'],author_report=json.loads((author/'report.json').read_text()),
       model='40 sparse short-time moving OSC atoms with L/R phase parameters; new residual excitation only for remaining spectrum',
       limits=['Acoustic projection, not a physical mechanical source classifier or measured RPM','Finite source-conditioned gesture score with fresh variations and independent pitch/duration controls; not a full statistical family of multiple real starts','No subjective improvement or main App integration claimed'],
       partition_exact=True,fresh_variations=True,unchanged_catch_and_idle_from_1_8s=True,outputs=outputs,human_accepted=False,app_changed=False)
    save(a.output/'verification.json',report);print(json.dumps(report,ensure_ascii=True))

if __name__=='__main__':main()
