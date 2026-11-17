"""Build a paired startup candidate with procedural C starter + existing C DNA.

Creates audio/files only; leaves the primary App, defaults and DLL untouched.
"""
import argparse,ctypes as C,hashlib,json
from copy import deepcopy
from pathlib import Path
import numpy as np
import soundfile as sf
from startup_character_v1.author import author
from startup_character_v1.native import Starter
from vehicle_controller.native import Bridge,Engine
from vehicle_controller import take

RATE=48000
def save(path,value):path.write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf-8')
def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()

def known(library,output):
    output.mkdir();paths=[]
    for k in range(3):
        p=output/f'{k}.sfir';p.write_text('VSL_SPECTRAL_TEXTURE 1 48000 2 0\n1 0.2 1\n1\n1 0.1 -1\n1\n',encoding='ascii');paths.append(dict(path=str(p)))
    profile=dict(profiles=paths,envelope=[1.]*9,variation=.1)
    progress=np.linspace(0,1,8191);gate=np.ones(len(progress),dtype=int);gate[4000:]=0
    def generate(chunk,strength=1.,seed=90107):
        s=Starter(library,profile,seed)
        try:return np.concatenate([s.process(progress[n:n+chunk],gate[n:n+chunk],strength) for n in range(0,len(gate),chunk)])
        finally:s.close()
    a=generate(8191);b=generate(217);half=generate(479,.5)
    assert np.array_equal(a,b) and np.array_equal(a*.5,half)
    assert not np.array_equal(a,generate(479,seed=90217))
    assert np.isfinite(a).all() and np.max(abs(a[-100:]))<.002
    save(output/'verification.json',dict(partition_exact=True,strength_linear=True,seeds_differ=True,release_decays=True))

def render_dna(bridge,control,response,automation,frames):
    pcm=[];observed=[];gate=np.zeros(frames,dtype=int);progress=np.zeros(frames);start=None
    with Engine(bridge,0,startup_response=response) as e:
        while e.frame<frames:
            frame=e.frame;c=deepcopy(control);c.update(ignition=int(frame>=28800),start_id=int(frame>=28800))
            if automation:
                c['gain']*=float(np.interp(frame/RATE,automation['seconds'],automation['gain']))
                c['dna']['pitch_follow']=float(np.interp(frame/RATE,[0,1.18,1.55,2.03,2.35,4],[.25,1,1,.7,.25,.25]))
            e.set(c);pcm.append(np.frombuffer(e.process(240),'<f4').copy().reshape(-1,2));state=e.state()
            observed.append(dict(frame=frame,**{k:state[k] for k in ['rpm','lifecycle','event_started']}))
            if state['lifecycle']==2:
                if start is None:start=frame
                gate[frame:frame+240]=1
                progress[frame:frame+240]=np.clip((np.arange(frame,frame+240)-start)/(response['crank_seconds']*RATE),0,1)
            elif start is not None:progress[frame:frame+240]=1
    return np.concatenate(pcm),observed,progress,gate

def main():
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True)
    p.add_argument('--catch-emphasis',type=float,default=2.0);p.add_argument('--starter-level',type=float,default=1.5);a=p.parse_args()
    if not 0<=a.catch_emphasis<=3 or not 0<a.starter_level<=3:p.error('Bounded emphasis 0..3 and starter level 0..3 required')
    repo=Path(__file__).resolve().parents[1];a.output.mkdir(parents=True,exist_ok=False)
    library=repo/'build-startup-character-v1/Release/startup_character_bridge.dll'
    # Meaningful lifecycle/source checks run before reading the real source.
    known(library,a.output/'known')
    source=Path('E:/VehicleSoundLab/references/clean/A_decoded_float.wav')
    profile=author(source,a.output/'model')
    original=json.loads(Path('E:/VehicleSoundLab/references/analysis/startup_enable_v1/verification1/V10-startup-enabled.vslpreset.json').read_text(encoding='utf-8'))
    b=Bridge(repo);control=deepcopy(original['control']);control.update(gear=0,automatic=0,mode=1,throttle=0.,brake=.65,ignition=0,start_id=0)
    control['input'].update(source=0,valid=0,sequence=0)
    old,oldstates,_,_=render_dna(b,control,original['startup_response'],None,4*RATE)
    candidate=deepcopy(control);candidate['events']['enabled']=0
    candidate['legacy_event_gain']=candidate['startup_gain']=candidate['catch_gain']=0
    response=dict(original['startup_response'],crank_seconds=.58,catch_rise_seconds=.30,catch_settle_seconds=.55,flare_rpm=1350.,combustion_seconds=.16)
    # Sparse, material-informed onset energy, followed by unmodified idle level.
    # RPM values remain engineering controls: no physical RPM inferred here.
    with sf.SoundFile(source) as f:
        f.seek(47*RATE);reference=f.read(4*RATE,dtype='float64')
    idle_ref=np.sqrt(np.mean(reference[round(2.6*RATE):round(3.6*RATE)]**2))
    times=np.linspace(1.18,2.03,7)
    energy=np.array([np.sqrt(np.mean(reference[round((t-.035)*RATE):round((t+.035)*RATE)]**2)) for t in times])
    lift=(energy-min(energy))/max(1e-12,max(energy)-min(energy))
    gains=1+a.catch_emphasis*lift
    automation=dict(seconds=[0.,.6,1.18,*times[1:].tolist(),2.35,4.],gain=[1.,1.,float(gains[0]),*gains[1:].tolist(),1.,1.])
    dna,states,progress,gate=render_dna(b,candidate,response,automation,4*RATE)
    idle_native=np.sqrt(np.mean(dna[round(2.6*RATE):round(3.6*RATE)].astype(float)**2))
    reference_gain=float(idle_native/idle_ref)
    strength=reference_gain*a.starter_level
    assert 0<strength<4
    outputs={};motor=[]
    for seed in (77317,88643):
        s=Starter(library,profile,seed)
        try:
            y=np.concatenate([s.process(progress[n:n+479],gate[n:n+479],strength) for n in range(0,len(gate),479)])
        finally:s.close()
        # Separate C voices, dry electrical sum only; no room or limiting.
        mix=dna+y
        assert np.isfinite(mix).all() and np.max(abs(mix))<.95
        name=f'Candidate-{seed}.wav';sf.write(a.output/name,mix,RATE,subtype='FLOAT')
        motor.append(y);outputs[name]=dict(sha256=digest(a.output/name),peak=float(np.max(abs(mix))))
    for name,x in [('Reference-exterior.wav',reference*reference_gain),('Previous-startup.wav',old),('DNA-only.wav',dna),('Starter-only.wav',motor[0])]:
        assert np.isfinite(x).all() and np.max(abs(x))<.95
        sf.write(a.output/name,x,RATE,subtype='FLOAT');outputs[name]=dict(sha256=digest(a.output/name),peak=float(np.max(abs(x))))
    assert not np.array_equal(motor[0],motor[1])
    assert np.max(abs(motor[0][round(2.0*RATE):]))<1e-10
    save(a.output/'telemetry.json',dict(candidate=states,previous=oldstates))
    save(a.output/'recipe.json',dict(control=candidate,startup_response=response,automation=automation,starter=profile,starter_strength=strength,
        catch_emphasis=a.catch_emphasis,starter_level=a.starter_level,reference_gain=reference_gain))
    # One additional block-size check on the real extracted profiles.
    s=Starter(library,profile,77317)
    try:other=np.concatenate([s.process(progress[n:n+217],gate[n:n+217],strength) for n in range(0,len(gate),217)])
    finally:s.close()
    assert np.array_equal(motor[0],other)
    active=(gate==1)&(np.arange(len(gate))>round(.64*RATE));target=reference[active]*strength
    measured=motor[0][active]
    def bands(x):
        from scipy import signal
        f,p=signal.welch(x,fs=RATE,nperseg=2048,noverlap=1024,axis=0)
        return [float(np.sum(p[(f>=lo)&(f<hi)])) for lo,hi in zip([0,60,300,1200,4500,14000],[60,300,1200,4500,14000,24001])]
    bp=np.array(bands(measured));tp=np.array(bands(target))
    def rms(x,t0,t1):return float(np.sqrt(np.mean(x[round(t0*RATE):round(t1*RATE)].astype(float)**2)))
    new=sf.read(a.output/'Candidate-77317.wav',always_2d=True)[0]
    report=dict(schema='vsl.startup-character-review/1',status='candidate_pending_listening',main_native_sha256=b.sha256,starter_native_sha256=digest(library),outputs=outputs,
        model=profile,known_checks_passed=True,real_profile_partition_exact=True,source_waveform_used_at_runtime=False,room=False,
        controls=dict(crank_seconds=.58,flare_rpm=1350.,idle_rpm=850.,rpm_evidence='Engineering contour, not ECU measured',catch_overlap='Old catch event disabled; only same DNA combustion establishes'),
        crank_band_error_db=(10*np.log10(bp/tp)).tolist(),bands_hz=[0,60,300,1200,4500,14000,24000],
        comparison_limits='Previous has old cabin-source events and different timing; new starter uses approved exterior spectral states. Combined candidate timing/voice/energy changed together; not a single-variable fidelity proof.',
        reference_gain=reference_gain,reference_level_policy='One constant gain from stable idle only, no segment normalization, dynamics or room',
        catch_over_idle_db=float(20*np.log10(rms(new,1.2,2.0)/rms(new,2.6,3.6))),
        human_accepted=False,app_integrated=False,accepted_idle_algorithm_changed=False)
    save(a.output/'verification.json',report)
    print(json.dumps(dict(status=report['status'],outputs=outputs,crank_band_error_db=report['crank_band_error_db']),ensure_ascii=True))

if __name__=='__main__':main()
