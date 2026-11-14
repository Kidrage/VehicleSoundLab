"""Independent source DFT/fit checks and full native candidate reconstruction."""
import argparse,shutil,sys
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__)
for key in ['workspace','fit','input','out']:p.add_argument('--'+key,type=Path,required=True)
a=p.parse_args();sys.path.insert(0,str(a.workspace/'tools/python_deps'))
import numpy as np
import soundfile as sf
from scipy import signal,interpolate
from research_archive_v1 import load,save,sha

a.out.mkdir(parents=True,exist_ok=False);shutil.copy2(__file__,a.out/'executed_auditor.py')
r=dict(result='running',fit_sha256=sha(a.fit/'report.json'),input_sha256=sha(a.input/'report.json'),source=[],renders=[])


def features(z):
    v=np.column_stack([z,z[:,1]*np.conj(z[:,0]),z[:,2]*np.conj(z[:,0]),z[:,2]*np.conj(z[:,1])])
    return np.concatenate([v.real,v.imag],axis=1)


def probability(model,x):
    logits=np.log(model['prior'])+np.column_stack([np.ones(len(x)),x])@np.asarray(model['coefficient'])
    ex=np.exp(logits-logits.max(axis=1,keepdims=True))
    return ex/ex.sum(axis=1,keepdims=True)


def innovation(seed,index,count,probabilities):
    key=seed^((0x9E3779B97F4A7C15*(index+1))&((1<<64)-1))
    if index<2:return np.random.Generator(np.random.PCG64(key^0x794323AA)).standard_normal(count)
    p=probabilities[index-2]
    u=np.random.Generator(np.random.PCG64(key^0x94D049BB133111EB)).random(count)
    n=np.random.Generator(np.random.PCG64(key^0xD1B54A32D192ED03)).standard_normal(count)
    return np.where(u<p,n/np.sqrt(p),0.)


try:
    fit=load(a.fit/'report.json');render=load(a.input/'report.json')
    assert fit['result']=='local_positive_shape_extraction_complete' and render['result']=='finite_local_shape_audio_pending_audit'
    origin=a.workspace/'baselines/idle_conditioned_detail_v1/evidence/observe1'
    q_coefficient=np.asarray(fit['law']['coefficients'])
    centers=np.arange(12000,132000,96);index=centers[:,None]+np.arange(-128,128)
    window=.5-.5*np.cos(2*np.pi*np.arange(256)/256)
    for row in fit['observations']:
        for part in ['train','check']:
            with np.load(origin/(part+'.npz')) as f:audio=f['audio'];z=f['phasors']
            if row['seed'] is not None:
                fft=np.fft.rfft(audio,axis=0)
                phase=np.random.default_rng(row['seed']).uniform(-np.pi,np.pi,len(fft));phase[[0,-1]]=0
                audio=np.fft.irfft(fft*np.exp(1j*phase[:,None]),n=len(audio),axis=0)
                with np.load(origin/f"{part}_phase_{row['seed']}.npz") as f:z=f['phasors']
            x=features(z);q=np.exp(q_coefficient[0]+x@q_coefficient[1:])
            with np.load(a.fit/f"{row['label']}_{part}.npz") as f:saved={k:f[k] for k in f.files}
            assert abs(x[centers]-saved['feature']).max()<1e-14
            errors=[]
            for band,item in enumerate(row['bands']):
                y=audio[:,0].copy()
                for section in saved['sos'][band]:y=signal.lfilter(section[:3],section[3:],y)
                y/=np.sqrt(q[:,band]);bins=saved[f'bins_{band}']
                transform=np.exp(-2j*np.pi*np.arange(256)[:,None]*bins[None,:]/256)
                spectrum=(y[index]*window)@transform
                power=abs(spectrum)**2;target=power/power.sum(axis=1,keepdims=True)
                error=float(abs(target-saved[f'shape_{band}']).max());assert error<1e-9
                predicted=probability(item['model'],x[centers])
                entropy=np.sum(target*np.log(target),axis=1)
                loss=float(np.mean(entropy-np.sum(target*np.log(predicted),axis=1)))
                old=float(np.mean(entropy-np.sum(target*np.log(item['model']['prior']),axis=1)))
                assert abs(loss-item['assessment'][part]['mean_KL'])<1e-10
                assert abs((1-loss/old)-item['assessment'][part]['improvement'])<1e-9
                if part=='train':
                    design=np.column_stack([np.ones(len(target)),x[centers]])
                    gradient=(design.T@(predicted-target)/len(target))[:,1:]
                    assert abs(abs(gradient).max()-item['model']['gradient_infinity'])<1e-10
                errors.append(error)
            r['source'].append(dict(label=row['label'],part=part,direct_native_DFT_probability_errors=errors))
    parent=a.workspace/'baselines';phase_root=parent/'idle_phase_recipe_v1/evidence/render2'
    model=load(phase_root/'model.json')
    profile=load(parent/'fixed_source_profiles_v1/evidence/trial1/F2_tailpipe/profile.json')
    allocated=load(parent/'idle_post_budget_v1/evidence/observe1/report.json')['allocation']['probability']
    banks=[]
    bank_digests=[]
    for b in range(2):
        with np.load(a.input/f'bank_{b}.npz') as f:bank={k:f[k] for k in f.files}
        bank_digests.append(sha(a.input/f'bank_{b}.npz'))
        reference=np.zeros(32768);reference[16384:16384+8192]=profile['kernels'][b+2]['taps']
        assert abs(bank['taps'].sum(axis=0)-reference).max()<1e-13
        # Independently rebuild every declared cell response, not only its sum.
        frequency=np.arange(16385)*48000/32768;centers=bank['centers_hz']
        mask=np.zeros((len(centers),len(frequency)))
        mask[0,frequency<=centers[0]]=1;mask[-1,frequency>=centers[-1]]=1
        middle=np.flatnonzero((frequency>centers[0])&(frequency<centers[-1]))
        lower=np.searchsorted(centers,frequency[middle],side='right')-1
        u=(frequency[middle]-centers[lower])/(centers[lower+1]-centers[lower])
        upper=.5-.5*np.cos(np.pi*u)
        mask[lower,middle]=1-upper;mask[lower+1,middle]=upper
        response=np.fft.rfft(bank['taps'],axis=1)
        assert abs(response-mask*np.fft.rfft(reference)).max()<3e-12
        gram=np.einsum('it,jt->ij',bank['taps'],bank['taps'],optimize=False)
        assert abs(gram-bank['gram']).max()<1e-13
        assert abs(np.sum(gram)-bank['reference_variance'])<1e-12
        banks.append(bank)
    M=np.array([[-1.,-1.,1.],[3.,-2.,0.]])
    right=np.linalg.solve(M@M.T,M).T
    for row in render['renders']:
        seed=row['seed'];frames=24*48000
        with np.load(a.input/row['trace']) as f:trace={k:f[k] for k in f.files}
        with np.load(phase_root/f'motion_{seed}.npz') as f:nodes=f['coordinate_nodes']
        motion=interpolate.CubicSpline((np.arange(len(nodes))-2)/model['node_rate'],nodes,bc_type='natural')
        probabilities=[np.empty_like(trace[f'probabilities_{b}']) for b in range(2)]
        q=np.empty_like(trace['q'])
        for first in range(0,frames,24000):
            stop=min(frames,first+24000);t=np.arange(first,stop)/48000
            theta=(model['carrier_phase_rad']+2*np.pi*model['carrier_hz']*t)[:,None]*[2,3,5]+motion(t)@right.T
            x=features(np.exp(1j*theta));q[first:stop]=np.exp(q_coefficient[0]+x@q_coefficient[1:])
            for b in range(2):probabilities[b][first:stop]=probability(render['models'][b],x)
        assert abs(q-trace['q']).max()<1e-10
        assert max(abs(probabilities[b]-trace[f'probabilities_{b}']).max() for b in range(2))<1e-11
        details={str(v):np.zeros((frames,2)) for v in [0.,.5,1.]};branch_error=variance_error=0.
        for index,kernel in enumerate(profile['kernels']):
            selected=index in [2,3];delay=16384 if selected else 0
            count=frames+profile['warmup_frames']+delay
            excitation=innovation(seed,index,count,allocated)
            length=1<<(count+32768-2).bit_length();xfft=np.fft.rfft(excitation,n=length)
            def convolution(h,start):
                return np.fft.irfft(xfft*np.fft.rfft(h,n=length),n=length)[start:start+frames]*kernel['gain']
            original=convolution(kernel['taps'],profile['warmup_frames'])
            ratio=np.array([1.,kernel['right_over_left']]);root=np.sqrt(q[:,index-2]) if index>=2 else np.ones(frames)
            if not selected:
                for y in details.values():y+=original[:,None]*root[:,None]*ratio
                continue
            b=index-2;bank=banks[b]
            branches=np.column_stack([convolution(h,profile['warmup_frames']+delay) for h in bank['taps']])
            branch_error=max(branch_error,float(abs(branches-trace[f'branches_{b}']).max()))
            assert branch_error<1e-12
            for amount in [0.,.5,1.]:
                if amount==0.:y=original
                else:
                    raw=np.power(probabilities[b]/render['models'][b]['prior'],amount*.5)
                    variance=np.sum((raw@bank['gram'])*raw,axis=1)
                    gains=raw*np.sqrt(bank['reference_variance']/variance)[:,None]
                    assert abs(gains-trace[f'gain_{b}_{amount}']).max()<1e-10
                    actual=np.sum((gains@bank['gram'])*gains,axis=1)
                    variance_error=max(variance_error,float(abs(actual-bank['reference_variance']).max()))
                    y=np.sum(gains*branches,axis=1)
                details[str(amount)]+=y[:,None]*root[:,None]*ratio
        main,rate=sf.read(phase_root/f'new_main_{seed}.wav',frames=frames,always_2d=True)
        current,_=sf.read(a.input/row['files']['main']['file'],always_2d=True)
        assert np.array_equal(main,current) and rate==48000
        errors={}
        for amount,y in details.items():
            for bus,oracle in [('detail',y),('mix',main+y)]:
                path=a.input/row['files'][bus+'_'+amount]['file'];assert sha(path)==row['files'][bus+'_'+amount]['sha256']
                actual,rate=sf.read(path,always_2d=True);error=float(abs(actual-oracle).max())
                assert rate==48000 and np.isfinite(actual).all() and abs(actual).max()<1. and error<3e-8
                errors[bus+'_'+amount]=error
        assert variance_error<1e-12
        r['renders'].append(dict(seed=seed,full_native_waveform_errors_FS=errors,
                                full_branch_convolution_error_FS=branch_error,
                                full_Gram_variance_error=variance_error))
        save(a.out/'report.json',r);print(dict(stage='audited',seed=seed,errors=errors),flush=True)
    r.update(result='passed',source_observations=8,all16models_checked=True,bank_sha256=bank_digests,
             every_compiled_branch_response_independently_checked=True,
             all_native_candidate_samples_checked=True,recorded_trajectory_replayed=False,
             check_is_previously_inspected_and_used_for_band_selection=True,runtime_changed=False,listening_accepted=False)
except Exception as exc:r.update(result='failed',error=repr(exc));raise
finally:save(a.out/'report.json',r)
