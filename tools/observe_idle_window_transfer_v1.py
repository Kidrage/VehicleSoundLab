"""Diagnose aperture transfer and source resolution without new synthesis variants."""
import argparse,os,shutil,sys
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__)
for key in ['workspace','out']:p.add_argument('--'+key,type=Path,required=True)
a=p.parse_args();repo=Path(__file__).resolve().parents[1];sys.path.insert(0,str(a.workspace/'tools/python_deps'))
for key in ['OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','OMP_NUM_THREADS']:os.environ[key]='2'
import numpy as np
from research_archive_v1 import load,save,sha
from idle_window_transfer_v1.observe import observe,known,design,CENTRES
from idle_window_transfer_v1.transfer import run,FREQUENCIES
from idle_variation_budget_v1.variation import summarize
from idle_conditioned_detail_v1.features import phases
from idle75_clock_v1.forward import predict

a.out.mkdir(parents=True,exist_ok=False);r=dict(result='running',sources={},inputs={},known={},transfer=[],cases=[])


def track(path):r['inputs'][str(path)]=sha(path);return path
def checkpoint():save(a.out/'report.json',r)
def record(label,audio,z,reference,metadata):
    for ms in [50,100,200]:
        coefficient,condition=observe(audio,freq,z,ms);s=summarize(coefficient[:,[1,2,4]],reference)
        file=a.out/f'{label}_{ms}.npz';np.savez_compressed(file,coefficients=coefficient,condition=condition,reference=reference,**s)
        r['cases'].append(dict(label=label,window_ms=ms,metadata=metadata,file=file.name,sha256=sha(file),
            std=s['std'].tolist(),rho=s['rho_100_200_500ms'].tolist(),max_condition=float(condition.max())))
    checkpoint();print(dict(label=label,windows=3),flush=True)


try:
    names=['tools/observe_idle_window_transfer_v1.py','tools/idle_window_transfer_v1/observe.py','tools/idle_window_transfer_v1/transfer.py',
        'tools/idle75_clock_v1/row.py','tools/idle75_clock_v1/forward.py','tools/idle_variation_budget_v1/variation.py',
        'tools/idle_conditioned_detail_v1/features.py','tools/research_archive_v1.py','research/idle_window_transfer_v1_plan.json']
    for name in names:
        dest=a.out/'exact_sources'/name;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(repo/name,dest);r['sources'][name]=sha(repo/name)
    root=a.workspace/'baselines';profile=load(track(root/'fixed_source_profiles_v1/evidence/trial1/F2_tailpipe/profile.json'))
    freq=np.array(profile['modal']['frequencies_hz']);r['known']['FM_noAM'],arrays=known(freq)
    np.savez_compressed(a.out/'known.npz',**arrays);checkpoint()
    frozen=root/'idle75_clock_v1/evidence/fit2';previous=load(track(frozen/'report.json'))
    reference=load(track(root/'idle_local_partition_v1/evidence/compile2/model.json'))['main_amplitude_LR'][0][0]
    for row in previous['streams']:
        with np.load(track(frozen/row['file'])) as f:h=f['response_h'];z=f['phasors'];constant=f['response_constant'];base=f['baseline_mix']
        controls,arrays=run(h,reference);r['transfer'].append(dict(seed=row['seed'],controls=controls))
        np.savez_compressed(a.out/f'transfer_{row["seed"]}.npz',**{f'{f}_{key}':value for f,items in arrays.items() for key,value in items.items()})
        # Verify cached response using actual waveform difference and full native projection.
        baseline=observe(base,freq,z,200)[0][:,1];t=np.arange(144000)/48000;errors=[]
        for f in FREQUENCIES:
            gain=1+.1*np.cos(2*np.pi*f*t);wave=base+.1*reference*z[:,0].real*np.cos(2*np.pi*f*t)
            actual=observe(wave,freq,z,200)[0][:,1]
            predicted=.1*reference*np.array(arrays[str(f)]['first'])[:,0]
            error=float(abs((actual-baseline).real-predicted).max()/reference);assert error<1e-10;errors.append(error)
        r['transfer'][-1]['native_wave_projection_errors']=errors;checkpoint()
    source=root/'idle_conditioned_detail_v1/evidence/observe1';varroot=root/'idle_variation_budget_v1/evidence/observe1'
    vr=load(track(varroot/'report.json'));lookup={row['label']:row for row in vr['cases']}
    for seed in [None,149921,277139,381611]:
        for part in ['train','check']:
            with np.load(track(source/(part+'.npz'))) as f:audio=f['audio'][:,0];z=f['phasors']
            label=('source' if seed is None else 'phase_'+str(seed))+'_'+part
            if seed is not None:
                fft=np.fft.rfft(audio);phase=np.random.default_rng(seed).uniform(-np.pi,np.pi,len(fft));phase[0]=phase[-1]=0
                audio=np.fft.irfft(fft*np.exp(1j*phase),n=len(audio))
                with np.load(track(source/f'{part}_phase_{seed}.npz')) as f:z=f['phasors']
            old=lookup[label];old_file=track(varroot/old['file']);assert sha(old_file)==old['sha256']
            with np.load(old_file) as f:ref=f['reference']
            record(label,audio,z,ref,dict(kind='source' if seed is None else 'samePSD_control',part=part,seed=seed,phase_basis='measured_acoustic'))
    for row in previous['streams']:
        with np.load(track(frozen/row['file'])) as f:base=f['baseline_mix'];z=f['phasors']
        for basis,phase in [('procedural',z),('measured_acoustic',phases(base,freq[[1,2,4]]))]:
            record(f'generated_{row["seed"]}_{basis}',base,phase,np.array([reference,
                load(root/'idle_local_partition_v1/evidence/compile2/model.json')['main_amplitude_LR'][1][0],
                load(root/'idle_local_partition_v1/evidence/compile2/model.json')['main_amplitude_LR'][2][0]]),
                dict(kind='generated',seed=row['seed'],phase_basis=basis,condition='1.0',block=0))
    assert len(r['cases'])==42
    r.update(result='idle_aperture_transfer_and_resolution_observed',new_source_fit=False,new_audio=False,new_C=False,
        temporal_statistics_not_native_excitation=True,known_two_pass_is_not_old_FIR_compiler=True)
except Exception as exc:r.update(result='failed',error=repr(exc));raise
finally:checkpoint()
print(dict(result=r['result'],cases=len(r['cases'])),flush=True)
