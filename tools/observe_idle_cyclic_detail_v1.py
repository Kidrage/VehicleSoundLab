"""Extract new idle texture evidence without altering unheard recipes."""
import argparse,shutil,sys
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__)
for key in ['workspace','out']:p.add_argument('--'+key,type=Path,required=True)
a=p.parse_args();repo=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(a.workspace/'tools/python_deps'))
import numpy as np
import soundfile as sf
from research_archive_v1 import load,save,sha
from idle_cyclic_detail_v1.observer import LAGS,BANDS,analytic,covariance,known
from idle_phase_recipe_v1.phase import phasors,spline
from idle_phase_recipe_v1.render2 import free_phasors

a.out.mkdir(parents=True,exist_ok=False)
r=dict(result='running',sources={},inputs={},observations=[])
def input_path(path):
    r['inputs'][str(path)]=sha(path);return path
def observe(label,group,part,seed,audio,z,meta):
    x,sos=analytic(audio);x=x[12000:-12000];z=z[12000:-12000]
    assert x.shape==(120000,4) and z.shape==(120000,3)
    c,denom=covariance(x,z);path=a.out/(label+'.npz')
    np.savez_compressed(path,analytic=x,phasors=z,covariance=c,denominator=denom,sos=sos,lags=LAGS)
    r['observations'].append(dict(label=label,group=group,part=part,seed=seed,file=path.name,
        sha256=sha(path),cyclic_absmax=float(abs(c).max()),metadata=meta))
    save(a.out/'report.json',r);print(label,flush=True)
try:
    names=['tools/observe_idle_cyclic_detail_v1.py','tools/idle_cyclic_detail_v1/observer.py',
        'tools/research_archive_v1.py','research/idle_cyclic_detail_v1_plan.json',
        'tools/idle_phase_recipe_v1/phase.py','tools/idle_phase_recipe_v1/render2.py',
        'tools/idle_positive_power_v1/model.py','tools/idle_phase_difference_v1/features.py',
        'tools/idle_modal_v1/modal.py','tools/idle_phase_recipe_v1/spectral.py']
    # Freeze direct dependencies that define the saved candidate clocks too.
    for name in names:
        path=repo/name
        if not path.exists():raise FileNotFoundError(path)
        target=a.out/'exact_sources'/name;target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(path,target);r['sources'][name]=sha(path)
    r['known'],arrays=known();np.savez_compressed(a.out/'known.npz',**arrays)
    origin=a.workspace/'baselines/idle_conditioned_detail_v1/evidence/observe1'
    for part in ['train','check']:
        path=input_path(origin/(part+'.npz'))
        with np.load(path) as f:audio=f['audio'];z=f['phasors']
        observe('source_'+part,'source',part,None,audio,z,dict(input=str(path)))
        for seed in [149921,277139,381611]:
            path=input_path(origin/f'{part}_phase_{seed}.npz')
            with np.load(path) as f:control_z=f['phasors']
            spectrum=np.fft.rfft(audio,axis=0)
            phase=np.random.default_rng(seed).uniform(-np.pi,np.pi,len(spectrum));phase[0]=phase[-1]=0
            control=np.fft.irfft(spectrum*np.exp(1j*phase[:,None]),n=len(audio),axis=0)
            assert abs(abs(np.fft.rfft(control,axis=0))-abs(spectrum)).max()<1e-10
            observe(f'phase_{seed}_{part}','phase_control',part,seed,control,control_z,
                dict(source_audio='source_'+part,phasors_input=str(path),same_magnitude_spectrum=True))
    render=a.workspace/'baselines/idle_phase_recipe_v1/evidence/render2'
    rendered=load(input_path(render/'report.json'))
    profile=load(input_path(Path(rendered['inputs']['profile']['path'])))
    model=load(input_path(render/'model.json'))
    for row in rendered['renders']:
        seed=row['seed'];motion_path=input_path(render/row['motion_file'])
        with np.load(motion_path) as f:
            assert 'coordinate_nodes' in f.files;values=f['coordinate_nodes']
        model_for_clock=dict(model);model_for_clock['coordinate_center']=model['coordinate_center']
        motion=spline(model_for_clock,values)
        for method in ['static','relation_full']:
            wave_path=input_path(render/row['files'][method]['file'])
            assert sha(wave_path)==row['files'][method]['sha256']
            for block in range(4):
                first=block*144000;audio,rate=sf.read(wave_path,start=first,frames=144000,always_2d=True)
                assert rate==48000 and len(audio)==144000
                t=np.arange(first,first+144000)/rate
                z=free_phasors(profile,t) if method=='static' else phasors(model_for_clock,motion,t)
                observe(f'{method}_{seed}_block{block}',method,block,seed,audio,z,
                    dict(input=str(wave_path),start_frame=first,frames=144000,motion=str(motion_path)))
    r.update(result='idle_signed_lag_structure_observed',bands_hz=BANDS,lags_frames=LAGS.tolist(),
        common_support_frames=119808,check_used_for_fit=False,new_audio_generated=False,
        runtime_changed=False,physical_RPM_or_noise_sources_identified=False,
        limits='Finite mixed-recording and same-recording CHECK; cyclic covariance is not unique mechanical causation or audible-quality evidence.')
except Exception as exc:r.update(result='failed',error=repr(exc));raise
finally:save(a.out/'report.json',r)
print(dict(result=r['result'],observations=len(r['observations'])),flush=True)
