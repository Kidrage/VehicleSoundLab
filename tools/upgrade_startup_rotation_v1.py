"""Freeze one new procedural crank against unchanged V3 catch/idle."""
import argparse,hashlib,json,shutil,time
from pathlib import Path
import numpy as np
import soundfile as sf
from startup_rotation_v1.author import build,shared_am,fir_from_psd,save,sha,RATE
from startup_rotation_v1.native import RotationStarter
from render_startup_expression_v1 import controls,dna,render,voice
from startup_character_v1.expression import ExpressionStarter

def native_voice(cls,library,profile,seed,ctrl,chunk):
    v=cls(library,profile,seed);pieces=[];frames=len(ctrl['progress'])
    try:
        for n in range(0,frames,chunk):pieces.append(v.expression(ctrl['progress'][n:n+chunk],ctrl['gate'][n:n+chunk],ctrl['strength'][n:n+chunk],ctrl['pitch'][n:n+chunk],ctrl['core'],ctrl['texture']))
        return np.concatenate(pieces)
    finally:v.close()

def main():
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    a.output.mkdir(parents=True,exist_ok=False);repo=Path(__file__).resolve().parents[1]
    # Known acoustic AM before applying the analysis to approved material.
    t=np.arange(round(.58*RATE))/RATE
    y=(1+.3*np.cos(2*np.pi*11*t)+.08*np.sin(4*np.pi*11*t))*sum(np.cos(2*np.pi*f*t+.2*k) for k,f in enumerate((200,450,720,860,1100,1700,3000,6000)))
    hz,_,_,known=shared_am(np.stack((y,y),axis=1));assert abs(hz-11)<.3,(hz,known)
    psd=np.ones(8193)*1e-8;h=fir_from_psd(psd);assert abs(np.dot(h,h)-np.trapezoid(psd,dx=RATE/16384))<1e-12
    save(a.output/'known-analysis.json',dict(flutter_hz=hz,expected=11.,FIR_power_exact=True,**known))
    ref=Path('E:/VehicleSoundLab/references/analysis/startup_expression_v1/listen2')
    recipe=json.loads((ref/'recipe.json').read_text());library=repo/'build-startup-character-v4/Release/startup_character_bridge.dll'
    model=build(Path('E:/VehicleSoundLab/references/clean/A_decoded_float.wav'),a.output/'model',ref/'model/crank/profile.json')
    profiles={name:json.loads((ref/f'model/{name}/profile.json').read_text()) for name in ('prelude','crank','catch')}
    # Freeze old models with rewritten local paths; same coefficients/bytes.
    for name,profile in profiles.items():
        target=a.output/'model'/('old-'+name);target.mkdir()
        for row in profile['profiles']:
            dest=target/Path(row['path']).name;shutil.copy2(row['path'],dest);row.update(path=str(dest.resolve()),sha256=sha(dest))
        save(target/'profile.json',profile)
    base,states,main_sha,response,control=dna(repo,recipe)
    previous,old_stems,sections,end=render(library,profiles,recipe,base,96337,479)
    frozen_old,_=sf.read(ref/'Candidate-96337.wav',dtype='float32');old_error=float(np.max(abs(previous-frozen_old)))
    assert old_error<2e-6,old_error
    data,_,_,_=controls(recipe,len(base));ctrl=data['crank']
    # Replace only crank. C already owns profiles/LUT; remaining action and
    # handoff have exactly the same arrays as the regenerated V3 comparison.
    calibration=native_voice(RotationStarter,library,model,84199,ctrl,479)*ctrl['weight'][:,None]
    start,stop=sections['crank'];span=slice(round(start*RATE),round(stop*RATE))
    level=float(np.sqrt(np.mean(old_stems['crank'][span].astype(float)**2))/np.sqrt(np.mean(calibration[span].astype(float)**2)))
    def candidate(seed,chunk):
        new=(native_voice(RotationStarter,library,model,seed,ctrl,chunk)*ctrl['weight'][:,None]*level).astype('float32')
        stems=dict(old_stems,crank=new);mix=np.zeros_like(base)
        for x in stems.values():mix+=x
        return mix,stems
    mix,stems=candidate(142867,479);partition,_=candidate(142867,217);fresh,_=candidate(152983,479)
    assert np.array_equal(mix,partition) and not np.array_equal(mix,fresh)
    # Only the crank/release region may differ from the re-generated V3.
    assert np.array_equal(mix[:round(start*RATE)],previous[:round(start*RATE)])
    assert np.array_equal(mix[round(stop*RATE):],previous[round(stop*RATE):])
    late=round((end+.3)*RATE);assert np.array_equal(mix[late:],base[late:])
    outputs={}
    def write(name,x):
        assert np.isfinite(x).all() and np.max(abs(x))<.95,(name,float(np.max(abs(x))))
        path=a.output/name;sf.write(path,x,RATE,subtype='FLOAT');outputs[name]=dict(sha256=sha(path),peak=float(np.max(abs(x))))
    write('Candidate.wav',mix);write('Previous-V3.wav',previous);write('Alternate-seed.wav',fresh)
    for name,x in stems.items():write(name+'.wav',x)
    write('Previous-crank.wav',old_stems['crank'])
    shutil.copy2(ref/'Reference-exterior-full.wav',a.output/'Reference-exterior-full.wav')
    outputs['Reference-exterior-full.wav']=dict(sha256=sha(a.output/'Reference-exterior-full.wav'))
    # Equal, fixed gains within full comparisons; no per-candidate matching.
    # level above is fixed on a DIFFERENT seed and saved, not adapted at run time.
    save(a.output/'recipe.json',dict(base_recipe=recipe,rotation_scale=level,calibration_seed=84199,listening_seed=142867,other_seed=152983,sections=sections))
    save(a.output/'telemetry.json',states);save(a.output/'control.json',dict(control=control,startup_response=response))
    np.savez(a.output/'stems.npz',**stems,mix=mix,base=base)
    save(a.output/'verification.json',dict(status='pending_human_listening',native_sha256=sha(library),main_native_sha256=main_sha,
        partition_exact=True,late_idle_exact=True,prelude_and_catch_unchanged=True,old_V3_optimized_error_max=old_error,
        fixed_level_calibrated_on_different_seed=level,source='Approved A exterior 47.60..48.18s',
        limits=['Single recorded startup, not a multi-start statistical family','Acoustic AM fit and peak widths do not identify physical shafts, gears or RPM','Measured envelope includes beating/noise; allocating AM to the procedural driver remains a listening hypothesis','Sustained OSC + fresh complex envelopes + residual source-colour FIR, no recorded waveform loop or room IR','Candidate is isolated; main App keeps its startup until human review'],
        app_integrated=False,human_accepted=False,outputs=outputs))
    shutil.copy2(library,a.output/'startup_character_bridge.dll')
    print(json.dumps(dict(status='pending_human_listening',rotation_scale=level,old_V3_error=old_error,outputs=outputs)),flush=True)
if __name__=='__main__':main()
