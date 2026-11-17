"""Extend approved exterior action coverage; do not rewrite earlier selections."""
import argparse,hashlib,json,shutil
from pathlib import Path
import numpy as np
import soundfile as sf
from startup_character_v1.ridges import fit,render
from startup_character_v1.author import minimum_phase_shape,write_profile
from startup_character_v1.expression import smooth_curve

RATE=48000
def save(path,obj):path.write_text(json.dumps(obj,ensure_ascii=False,indent=2),encoding='utf-8')
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def make(source,out,start,stop,count,options):
    out.mkdir()
    with sf.SoundFile(source) as f:
        assert f.samplerate==RATE and f.channels==2
        f.seek(round(start*RATE));x=f.read(round((stop-start)*RATE),dtype='float64')
    positions=np.arange(len(x))/len(x)
    # Nine coarse level controls, not a saved sample-by-sample gain trajectory.
    bins=np.array_split(x,9);env=np.array([np.sqrt(np.mean(z*z)) for z in bins])
    env=np.maximum(env,np.mean(env)*.12);env/=np.mean(env)
    contour=smooth_curve(positions,np.linspace(0,1,9),env)
    normalized=x/contour[:,None]
    atoms,core,left=fit(normalized,count,**options)
    assert np.max(abs(render(atoms,len(x))-core))<1e-12
    profiles=[]
    for k,part in enumerate(np.array_split(left,3)):
        p=out/f'residual-{k}.sfir'
        write_profile(p,[minimum_phase_shape((part[:,0]+part[:,1])/np.sqrt(2)),minimum_phase_shape((part[:,0]-part[:,1])/np.sqrt(2))])
        profiles.append(dict(path=str(p.resolve()),sha256=sha(p)))
    doc=dict(schema='vsl.startup-expression-gesture/1',profiles=profiles,envelope=env.tolist(),variation=.08,
        ridges=atoms,reference_frames=len(x),ridge_variation=.06,ridge_pitch=1.,
        source=str(source),source_sha256=sha(source),seconds=[start,stop],
        room=False,pcm_playback=False,physical_source_separation=False,
        meaning='Finite source-conditioned acoustic gesture, independently editable pitch/duration/core/texture; no measured RPM or multiple-start statistical qualification')
    save(out/'profile.json',doc)
    save(out/'report.json',dict(atoms=len(atoms),source_seconds=[start,stop],
        normalized_waveform_projection_explained=float(1-np.sum(left*left)/np.sum(normalized*normalized)),
        metric_meaning='Same-excerpt representation capacity only, not hearing or a physical mechanical fraction'))
    np.savez(out/'decomposition.npz',source=x,core=core*contour[:,None],residual=left*contour[:,None])
    return doc


def main():
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    a.output.mkdir(parents=True,exist_ok=False)
    source=Path('E:/VehicleSoundLab/references/clean/A_decoded_float.wav')
    # Observed additional actions, deliberately kept separate from the old crop.
    sections=[('prelude',47.28,47.60,12,dict(lengths=(1024,2048,4096),hop=512,hz_range=(100.,6000.))),
              ('catch',48.18,49.65,48,dict(lengths=(4096,8192,16384),hop=1536,hz_range=(45.,2400.),slews=(-1600.,-800.,0.,800.,1600.)))]
    models={}
    for name,start,stop,count,options in sections:
        print('Authoring '+name,flush=True);models[name]=make(source,a.output/name,start,stop,count,options)
        print(json.dumps(json.loads((a.output/name/'report.json').read_text())),flush=True)
    # Preserve existing approved-source crank extraction; only the action controls change.
    original=Path('E:/VehicleSoundLab/references/analysis/startup_rhythm_v1/author1')
    out=a.output/'crank';out.mkdir();doc=json.loads((original/'profile.json').read_text())
    for row in doc['profiles']:
        path=out/Path(row['path']).name;shutil.copy2(row['path'],path);row.update(path=str(path.resolve()),sha256=sha(path))
    save(out/'profile.json',doc);models['crank']=doc
    save(a.output/'selection.json',dict(source=str(source),source_sha256=sha(source),
        new_observed_ranges={'prelude':[47.28,47.60],'catch':[48.18,49.65]},
        unchanged_crank_range=[47.60,48.18],basis='Full approved A exterior startup context 47..56s; previous narrow crop omitted precursor and late flare',
        physical_identity='Acoustic action labels only; no verified gear engagement or ECU RPM',
        models={k:str((a.output/k/'profile.json').resolve()) for k in models}))

if __name__=='__main__':main()
