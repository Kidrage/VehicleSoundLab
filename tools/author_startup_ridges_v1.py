"""Author sparse moving OSC core and residual colour for the same startup."""
import argparse,json
from pathlib import Path
import numpy as np,soundfile as sf
from startup_character_v1.ridges import fit,known,render
from startup_character_v1.author import minimum_phase_shape,write_profile

def main():
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);a=p.parse_args();a.output.mkdir(parents=True,exist_ok=False)
    result=dict(status='running',known=known());(a.output/'known.json').write_text(json.dumps(result),encoding='utf-8')
    old=Path('E:/VehicleSoundLab/references/analysis/startup_character_v1/attempt2/model/profile.json');profile=json.loads(old.read_text(encoding='utf-8'))
    with sf.SoundFile(profile['source']) as f:f.seek(round(47.6*48000));x=f.read(round(.58*48000),always_2d=True)
    t=np.arange(len(x))/len(x)*8;i=np.minimum(t.astype(int),7);u=t-i;u=u*u*(3-2*u)
    env=np.array(profile['envelope']);contour=(1-u)*env[i]+u*env[i+1]
    normalized=x/contour[:,None]
    atoms,core,remainder=fit(normalized,40)
    assert np.max(abs(render(atoms,len(x))-core))<1e-12
    output=[]
    for k,part in enumerate(np.array_split(remainder,3)):
        path=a.output/f'residual-{k}.sfir'
        write_profile(path,[minimum_phase_shape((part[:,0]+part[:,1])/np.sqrt(2)),minimum_phase_shape((part[:,0]-part[:,1])/np.sqrt(2))])
        output.append(dict(path=str(path)))
    profile.update(schema='vsl.startup-character-ridges/1',profiles=output,ridges=atoms,variation=0.10,
       ridge_pitch=1.,ridge_variation=.08,ridge_count=len(atoms),reference_frames=len(x),
       phase='Bounded moving-OSC initial phases retained as parameters; residual source phase discarded',
       meaning='Sparse acoustic chirplet score plus new residual excitation. Not physical starter/RPM separation; sparse source-conditioned score with editable pitch/duration and fresh variations.')
    (a.output/'profile.json').write_text(json.dumps(profile,ensure_ascii=False,indent=2),encoding='utf-8')
    result.update(status='authored_pending_C_and_listening',atoms=len(atoms),core_explained_waveform_energy=float(1-np.sum(remainder**2)/np.sum(normalized**2)),source_frames=len(x))
    (a.output/'report.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    np.savez(a.output/'decomposition.npz',source=x,core=core*contour[:,None],remainder=remainder*contour[:,None],contour=contour)
    print(json.dumps(result),flush=True)

if __name__=='__main__':main()
