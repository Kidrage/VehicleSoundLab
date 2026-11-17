"""Render one extended C-synthesized startup, followed by the existing C idle.

The foreground catch gesture replaces continuous-engine output during catch;
it is not a second complete engine added on top. The main App is untouched.
"""
import argparse,hashlib,json,shutil
from copy import deepcopy
from pathlib import Path
import numpy as np
import soundfile as sf
from startup_character_v1.expression import ExpressionStarter,smooth_curve
from vehicle_controller.native import Bridge,Engine

RATE=48000
ROOT=Path('E:/VehicleSoundLab/references/analysis')
def save(path,obj):path.write_text(json.dumps(obj,ensure_ascii=False,indent=2),encoding='utf-8')
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def default_recipe():
    previous=json.loads((ROOT/'startup_character_v1/attempt2/recipe.json').read_text())
    return dict(schema='vsl.startup-expression-recipe/1',seconds=7.,start_seconds=.45,
        prelude_seconds=.36,crank_seconds=1.10,catch_rise_seconds=.60,catch_settle_seconds=1.50,
        handoff_seconds=.70,reference_gain=previous['reference_gain'],
        prelude=dict(level=2.2,core=1.25,texture=.65,pitch_knots=[0.,.5,1.],pitch=[.9,1.05,1.12]),
        crank=dict(level=2.6,core=1.35,texture=.80,pitch_knots=[0.,.3,.7,1.],pitch=[.82,1.,1.12,1.20]),
        catch=dict(level=2.2,core=1.15,texture=.95,pitch_knots=[0.,.28,.60,1.],pitch=[.82,1.22,1.09,1.]),
        engineering_flare_rpm=2150.,rpm_evidence='Control trajectory only, not measured source RPM',
        human_accepted=False,room=False,PCM_playback=False)


def dna(repo,recipe):
    previous=json.loads((ROOT/'startup_character_v1/attempt2/recipe.json').read_text())
    control=deepcopy(previous['control']);control['events']['enabled']=0
    control['legacy_event_gain']=control['startup_gain']=control['catch_gain']=0
    response=dict(previous['startup_response'],crank_seconds=recipe['crank_seconds'],
        catch_rise_seconds=recipe['catch_rise_seconds'],catch_settle_seconds=recipe['catch_settle_seconds'],
        flare_rpm=recipe['engineering_flare_rpm'])
    b=Bridge(repo);pcm=[];states=[];frames=round(recipe['seconds']*RATE)
    crank_start=recipe['start_seconds']+recipe['prelude_seconds']
    with Engine(b,0,startup_response=response) as e:
        while e.frame<frames:
            frame=e.frame;t=frame/RATE;c=deepcopy(control)
            c.update(ignition=int(t+1e-10>=recipe['start_seconds']),start_id=int(t+1e-10>=crank_start))
            e.set(c);pcm.append(np.frombuffer(e.process(min(240,frames-frame)),'<f4').copy().reshape(-1,2))
            s=e.state();states.append(dict(frame=frame,reported_frame=s['frame'],**{k:s[k] for k in ('rpm','lifecycle','event_started','idle_weight')}))
    assert max(s['event_started'] for s in states)==0
    return np.concatenate(pcm),states,b.sha256,response,control


def controls(recipe,frames):
    t=np.arange(frames)/RATE;s=recipe['start_seconds'];p=s+recipe['prelude_seconds']
    c=p+recipe['crank_seconds'];end=c+recipe['catch_rise_seconds']+recipe['catch_settle_seconds']
    sections={'prelude':(s,p),'crank':(p,c),'catch':(c,end)}
    # Squared weights sum to one: crossfade, not two full engines at catch.
    hand=smooth_curve(t,[end-recipe['handoff_seconds'],end],[0,1]);w_dna=np.sin(np.pi*.5*hand)
    w_catch=np.cos(np.pi*.5*hand);w_catch[t>=end]=0.
    data={}
    for name,(start,stop) in sections.items():
        progress=np.clip((t-start)/(stop-start),0,1);gate=((t>=start-1e-10)&(t<stop-1e-10)).astype(np.int32)
        row=recipe[name];pitch=smooth_curve(progress,row['pitch_knots'],row['pitch'])
        level=np.ones(frames)*recipe['reference_gain']*row['level']
        # Give the final source-conditioned oscillator support a short fade,
        # while the existing C module releases its stochastic source at gate off.
        edge=smooth_curve(t,[stop-.035,stop],[1,0]) if name!='catch' else w_catch
        data[name]=dict(progress=progress,gate=gate,strength=level,pitch=pitch,core=row['core'],texture=row['texture'],weight=edge)
    return data,w_dna,sections,end


def voice(library,profile,seed,ctrl,chunk):
    v=ExpressionStarter(library,profile,seed);frames=len(ctrl['progress'])
    try:
        return np.concatenate([v.expression(ctrl['progress'][n:n+chunk],ctrl['gate'][n:n+chunk],ctrl['strength'][n:n+chunk],
            ctrl['pitch'][n:n+chunk],ctrl['core'],ctrl['texture']) for n in range(0,frames,chunk)])
    finally:v.close()


def render(library,profiles,recipe,source_dna,seed,chunk):
    data,dna_weight,sections,end=controls(recipe,len(source_dna));stems={}
    for k,name in enumerate(('prelude','crank','catch')):
        x=voice(library,profiles[name],seed+1009*k,data[name],chunk)
        stems[name]=(x*data[name]['weight'][:,None]).astype('float32')
    stems['idle_handoff']=(source_dna*dna_weight[:,None]).astype('float32')
    mix=np.zeros_like(source_dna)
    for stem in stems.values():mix+=stem
    assert np.isfinite(mix).all() and np.max(abs(mix))<.95
    return mix,stems,sections,end


def main():
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);p.add_argument('--recipe',type=Path);a=p.parse_args()
    repo=Path(__file__).resolve().parents[1];library=repo/'build-startup-character-v3/Release/startup_character_bridge.dll'
    a.output.mkdir(parents=True,exist_ok=False)
    recipe=json.loads(a.recipe.read_text(encoding='utf-8')) if a.recipe else default_recipe()
    author=ROOT/'startup_expression_v1/author1';profiles={};model=a.output/'model';model.mkdir()
    for name in ('prelude','crank','catch'):
        profile=json.loads((author/name/'profile.json').read_text());dest=model/name;dest.mkdir()
        for row in profile['profiles']:
            target=dest/Path(row['path']).name;shutil.copy2(row['path'],target);row.update(path=str(target.resolve()),sha256=sha(target))
        save(dest/'profile.json',profile);profiles[name]=profile
    save(a.output/'recipe.json',recipe)
    print('Rendering existing continuous C DNA and lifecycle',flush=True)
    base,states,base_sha,response,control=dna(repo,recipe);save(a.output/'telemetry.json',states)
    save(a.output/'base-control.json',dict(control=control,startup_response=response))
    mix,stems,sections,end=render(library,profiles,recipe,base,96337,479)
    print('Checking another seed and block partition',flush=True)
    again,other,_,_=render(library,profiles,recipe,base,96337,217)
    assert np.array_equal(mix,again)
    fresh,_,_,_=render(library,profiles,recipe,base,107071,479)
    assert not np.array_equal(mix,fresh)
    late=round((end+.30)*RATE)
    assert np.array_equal(mix[late:],base[late:]) and np.array_equal(fresh[late:],base[late:])
    outputs={}
    def write(name,x):
        assert np.isfinite(x).all() and np.max(abs(x))<.95
        path=a.output/name;sf.write(path,x,RATE,subtype='FLOAT');outputs[name]=dict(sha256=sha(path),peak=float(np.max(abs(x))))
    write('Candidate-96337.wav',mix);write('Alternate-seed-107071.wav',fresh)
    for name,x in stems.items():write(name+'.wav',x)
    write('Continuous-DNA.wav',base)
    with sf.SoundFile('E:/VehicleSoundLab/references/clean/A_decoded_float.wav') as f:
        f.seek(47*RATE);reference=f.read(len(mix),dtype='float64')
    write('Reference-exterior-full.wav',reference*recipe['reference_gain'])
    previous=ROOT/'startup_rhythm_v1/listen1/Candidate-45943.wav'
    shutil.copy2(previous,a.output/'Previous.wav');outputs['Previous.wav']=dict(sha256=sha(previous))
    def rms(x,start,stop):return float(np.sqrt(np.mean(x[round(start*RATE):round(stop*RATE)].astype(float)**2)))
    crank=sections['crank'];catch=sections['catch'];idle=(end+.4,recipe['seconds']-.3)
    report=dict(schema='vsl.startup-expression-review/1',status='pending_human_listening',
        native_sha256=sha(library),main_native_sha256=base_sha,
        sections_seconds=sections,total_gesture_seconds=end-recipe['start_seconds'],handoff_complete_seconds=end,
        previous_total_gesture_seconds=.58+.30+.55,
        controls_units='Pitch controls are acoustic multipliers. Engineering lifecycle RPM is not inferred from source spectra.',
        preset_response=response,
        source_catch_replaces_continuous_engine=True,catch_weight_rule='sin/cos equal-power handoff; only one full engine before and after overlap',
        late_idle_PCM_exact_to_same_C_run=True,partition_exact=True,fresh_variation=True,legacy_event_started=0,
        catch_over_idle_db=20*np.log10(rms(mix,*catch)/rms(mix,*idle)),
        crank_over_idle_db=20*np.log10(rms(mix,*crank)/rms(mix,*idle)),
        source_relative_levels={k:recipe[k]['level'] for k in sections},
        limits=['Finite source-conditioned gesture, not measured RPM or physical source separation',
                'Three acoustic layers of each gesture: moving OSC plus three-stage residual colour; no original PCM playback',
                'Original recording perspective remains in learned source spectra; no added room/reverb',
                'Candidate changes action duration/voice/pitch/layer balance together; not a single-variable fidelity test',
                'Foreground handoff is an isolated audition arrangement, not main-App routing or production event policy'],
        human_accepted=False,app_integrated=False,acceleration_fade_fixed=False,outputs=outputs)
    save(a.output/'verification.json',report);shutil.copy2(library,a.output/'startup_character_bridge.dll')
    print(json.dumps({k:report[k] for k in ('status','total_gesture_seconds','handoff_complete_seconds','catch_over_idle_db','crank_over_idle_db','partition_exact','late_idle_PCM_exact_to_same_C_run','outputs')}),flush=True)
if __name__=='__main__':main()
