"""Locate complete24s idle fast variation in actual buses and near75residual."""
import argparse,os,shutil,sys
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__)
for key in ['workspace','out']:p.add_argument('--'+key,type=Path,required=True)
a=p.parse_args();repo=Path(__file__).resolve().parents[1];sys.path.insert(0,str(a.workspace/'tools/python_deps'))
for key in ['OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','OMP_NUM_THREADS']:os.environ[key]='2'
import numpy as np
import soundfile as sf
from research_archive_v1 import load,save,sha
from idle_short_budget_v1.observe import observe,known as aperture_known
from idle_short_budget_v1.spectral import project,summarize as spectral,known as spectral_known
from idle_variation_budget_v1.variation import summarize,budget,known as budget_known
from idle_conditioned_detail_v1.features import phases
from idle_phase_recipe_v1.phase import spline,phasors

a.out.mkdir(parents=True,exist_ok=False);r=dict(result='running',sources={},inputs={},known={},cases=[],spectra=[])


def track(path):r['inputs'][str(path)]=sha(path);return path
def checkpoint():save(a.out/'report.json',r)
def record(label,buses,z,reference,metadata):
    for ms in [50,100,200]:
        c,condition=observe(buses,freq,z,ms);result=summarize(c[:,0,[1,2,4]],reference);b=budget(c[:,:,[1,2,4]],reference)
        identity=float(abs(c[:,0]-c[:,1]-c[:,2]).max());assert identity<1e-10
        file=a.out/f'{label}_{ms}.npz';np.savez_compressed(file,coefficients=c,reference=reference,condition=condition,**result,**b)
        r['cases'].append(dict(label=label,window_ms=ms,metadata=metadata,file=file.name,sha256=sha(file),
            std=result['std'].tolist(),main_std=b['main_std'].tolist(),detail_std=b['detail_std'].tolist(),
            lag0_signed_variance_ratios=b['lag0_signed_variance_ratios'].tolist(),coefficient_sum_error=identity))
    spectrum(label,buses,z,metadata);checkpoint()
def spectrum(label,buses,z,metadata):
    residual,beta=project(buses,freq,z);result=spectral(buses,residual,z)
    file=a.out/f'{label}_spectral.npz';np.savez_compressed(file,beta=beta,**result)
    r['spectra'].append(dict(label=label,metadata=metadata,file=file.name,sha256=sha(file),
        summary={key:value.tolist() for key,value in result.items()}))


try:
    names=['tools/observe_idle_short_budget_v1.py','tools/idle_short_budget_v1/observe.py','tools/idle_short_budget_v1/spectral.py',
        'tools/idle_variation_budget_v1/variation.py','tools/idle_window_transfer_v1/observe.py',
        'tools/idle_conditioned_detail_v1/features.py','tools/idle_phase_recipe_v1/phase.py',
        'tools/research_archive_v1.py','research/idle_short_budget_v1_plan.json']
    for name in names:
        dest=a.out/'exact_sources'/name;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(repo/name,dest);r['sources'][name]=sha(repo/name)
    root=a.workspace/'baselines';profile=load(track(root/'fixed_source_profiles_v1/evidence/trial1/F2_tailpipe/profile.json'))
    freq=np.array(profile['modal']['frequencies_hz'])
    r['known']['aperture'],arrays=aperture_known(freq);np.savez_compressed(a.out/'known_aperture.npz',**arrays)
    r['known']['budget'],arrays=budget_known();np.savez_compressed(a.out/'known_budget.npz',**arrays)
    r['known']['spectral'],arrays=spectral_known(freq);np.savez_compressed(a.out/'known_spectral.npz',**arrays)
    checkpoint()
    original=root/'idle_window_transfer_v1/evidence/observe1';pr=load(track(original/'report.json'))
    origin=root/'idle_conditioned_detail_v1/evidence/observe1'
    for row in pr['cases']:
        if row['metadata']['kind']=='generated':continue
        source=track(original/row['file']);assert sha(source)==row['sha256']
        target=a.out/row['file'];shutil.copy2(source,target)
        r['cases'].append(dict(row,reused_independently_audited_source=True))
        if row['window_ms']!=200:continue
        meta=row['metadata']
        with np.load(track(origin/(meta['part']+'.npz'))) as f:audio=f['audio'][:,0];z=f['phasors']
        if meta['seed'] is not None:
            fft=np.fft.rfft(audio);phase=np.random.default_rng(meta['seed']).uniform(-np.pi,np.pi,len(fft));phase[0]=phase[-1]=0
            audio=np.fft.irfft(fft*np.exp(1j*phase),n=len(audio))
            with np.load(track(origin/f'{meta["part"]}_phase_{meta["seed"]}.npz')) as f:z=f['phasors']
        spectrum(row['label'],audio[:,None],z,meta);checkpoint()
    generated=root/'idle_local_partition_v1/evidence/render1';render=load(track(generated/'report.json'))
    model=load(track(root/'idle_local_partition_v1/evidence/compile2/model.json'));reference=np.array(model['main_amplitude_LR'])[:,0]
    phase_root=root/'idle_phase_recipe_v1/evidence/render2';phase_model=load(track(phase_root/'model.json'))
    for row in render['renders']:
        seed=row['seed'];waves={}
        for bus in ['mix','main']:
            entry=row['files'][bus+'_1.0'];file=track(generated/entry['file']);assert sha(file)==entry['sha256']
            wave,rate=sf.read(file,always_2d=True);assert rate==48000 and len(wave)==1152000;waves[bus]=wave[:,0]
        with np.load(track(phase_root/f'motion_{seed}.npz')) as f:motion=spline(phase_model,f['coordinate_nodes'])
        for block,start in enumerate(range(0,1152000,144000)):
            mix=waves['mix'][start:start+144000];main=waves['main'][start:start+144000];buses=np.column_stack((mix,main,mix-main))
            z0=phasors(phase_model,motion,np.arange(start,start+144000)/48000);z1=phases(mix,freq[[1,2,4]])
            for basis,z in [('procedural',z0),('measured_acoustic',z1)]:
                record(f'generated_{seed}_{block}_{basis}',buses,z,reference,
                    dict(kind='generated',seed=seed,block=block,first_frame=start,phase_basis=basis,condition='1.0'))
            print(dict(seed=seed,block=block,phase_bases=2,apertures=3),flush=True)
    assert len(r['cases'])==168 and len(r['spectra'])==56
    r.update(result='complete_idle_short_bus_and_near75_budget_observed',new_source_fit=False,new_audio=False,new_C=False,
        source_physical_bus_separation=False,source_phase_observer_is_mix_conditioned=True)
except Exception as exc:r.update(result='failed',error=repr(exc));raise
finally:checkpoint()
print(dict(result=r['result'],cases=len(r['cases']),spectra=len(r['spectra'])),flush=True)
