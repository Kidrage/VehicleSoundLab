"""Replay every whole stream independently and verify every native observation and full pooled complex spectrum."""
import argparse,math,os,shutil,sys
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__)
for key in ['workspace','input','out']:p.add_argument('--'+key,type=Path,required=True)
a=p.parse_args();repo=Path(__file__).resolve().parents[1];sys.path.insert(0,str(a.workspace/'tools/python_deps'))
for key in ['OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','OMP_NUM_THREADS']:os.environ[key]='2'
import numpy as np
from scipy import signal
from research_archive_v1 import load,save,sha

a.out.mkdir(parents=True,exist_ok=False);shutil.copy2(__file__,a.out/'executed_auditor.py')
r=dict(result='running',input_sha256=sha(a.input/'report.json'),errors={},cases=0,records=0,blocks=0,window_CSDs=0,scalar_power_windows=0)
SEEDS=[(464437,137591),(606181,286049),(780991,471217)]


def check(name,x,y,gate=1e-10,relative=False):
    x=np.asarray(x);y=np.asarray(y);error=float(abs(x-y).max())
    if relative:
        scale=float(max(abs(x).max(),abs(y).max()))
        if scale:error/=scale
    r['errors'][name]=max(error,r['errors'].get(name,0.));assert error<=gate,(name,error,gate)


def energy(x,tile,P):
    n=len(tile);native=x.reshape(n,480,4);power=np.einsum('wsi,wsi->wi',native,native)/480
    for k in sorted(set([0,1,n//2,n-1])):
        direct=[math.fsum(float(v*v) for v in native[k,:,i])/480 for i in range(4)]
        check('scalar_native_power_windows',direct,power[k],1e-10,True);r['scalar_power_windows']+=1
    residual=power.copy()
    for tag in np.unique(tile):
        indices=np.flatnonzero(tile==tag);mean=np.array([math.fsum(power[indices,i])/len(indices) for i in range(4)]);residual[indices]-=mean
    values=[];counts=[]
    for lag in range(-5,6):
        left=np.arange(max(0,-lag),min(n,n-lag));right=left+lag;same=tile[left]==tile[right];left=left[same];right=right[same]
        values.append(np.array([[math.fsum(residual[left,i]*residual[right,j])/len(left) for j in range(4)] for i in range(4)]));counts.append(len(left))
    values=np.array(values);mean=np.array([math.fsum(power[:,i])/len(power) for i in range(4)])
    return dict(power=power,power_mean=mean,signed_lagged=values,theoretical_normalized=values/np.outer(P,P),
                measured_normalized=values/np.outer(mean,mean),lag_counts=np.array(counts))


def spectrum(x,N=12000):
    C=np.empty((N//2+1,4,4),complex)
    for i in range(4):
        for j in range(i,4):
            _,C[:,i,j]=signal.csd(x[:,i],x[:,j],fs=48000,window='hann',nperseg=N,noverlap=N//2,nfft=N,detrend='constant',scaling='density')
            if j!=i:C[:,j,i]=C[:,i,j].conj()
    return C


def gain_sequence(L,tau,frames,seed):
    rng=np.random.default_rng(seed);initial=L@rng.standard_normal(4);white=rng.standard_normal((frames,4));rate=1/(48000*tau)
    rho=math.exp(-rate);b=math.sqrt(2*math.exp(-rate)*math.sinh(rate));innovations=(white@L.T)*b
    latent=np.empty_like(white);state=initial.copy()
    # Closed finite geometric sums, not production lfilter. 512 samples keep all weights well-scaled.
    for start in range(0,frames,512):
        stop=min(frames,start+512);weights=np.exp(-np.arange(1,stop-start+1)*rate)
        latent[start:stop]=weights[:,None]*(state[None]+np.cumsum(innovations[start:stop]/weights[:,None],axis=0));state=latent[stop-1]
    previous=np.vstack((initial,latent[:-1]));check('complete_OU_recurrence',latent,rho*previous+innovations,1e-10)
    for k in [0,1,479,511,512,8191,frames-1]:
        check('scalar_OU_innovations',innovations[k],b*(L@white[k]),1e-12)
    return np.exp(latent-np.diag(L@L.T))


try:
    run=load(a.input/'report.json');assert run['result']=='all12_continuous_source_realizations_and576observations_complete'
    assert run['seed_pairs']==[list(x) for x in SEEDS] and run['continuous_blocks']==8
    for name,digest in run['sources'].items():assert sha(repo/name)==digest==sha(a.input/'exact_sources'/name)
    assert sha(a.input/'known.npz')==run['known_sha256']
    with np.load(a.input/'known.npz') as f:
        k=energy(f['audio'],f['tile'],f['theoretical_power'])
        for name in ['power','signed_lagged','theoretical_normalized','measured_normalized']:check('known_'+name,k[name],f[name],1e-12)
        check('known_Scipy_CSD',spectrum(f['audio']),f['spectrum'],1e-10,True)
        q=f['filter'];history=f['history'];direct=np.array([[math.fsum(q[j,i]*history[n-j,i] for j in range(3)) for i in range(4)] for n in range(2,len(history))])
        check('known_history_convolution',direct,f['filtered'],1e-12);check('known_explicit_filter',direct,f['explicit_filtered'],1e-12)
    parent=a.workspace/'baselines/accel_upper_coloured_v1';assert sha(parent/'manifest.json')==run['parent_manifest_sha256'];table={v['path']:v['sha256'] for v in load(parent/'manifest.json')['files']}
    for name,digest in run['parent_files'].items():assert sha(parent/name)==digest==table[name]
    fitted=load(parent/'evidence/fit1/report.json')
    for row,fr in zip(run['observations'],fitted['observations']):
        assert row['segment']==fr['segment'] and row['branch']==fr['branch'] and row['fit_available']==fr['fit']['available']
        assert sha(a.input/row['file'])==row['sha256']
        with np.load(a.input/row['file']) as model,np.load(parent/row['model_parent_file']) as old,np.load(parent/row['carrier_parent_file']) as carrier:
            for key,other in [('energy_expected','prediction'),('source_target','target'),('parameters','parameters'),('tile','tile'),('Welch_raw_expected','Welch_gain'),('Welch_refilter_expected','Welch_refilter_gain')]:check('frozen_'+key,model[key],old[other],0)
            h=old['impulse'];q=carrier['q'];warm=len(q)-1;tile=model['tile'];frames=len(tile)*480*8
            check('theoretical_coordinate_power',model['theoretical_power'],np.diag(carrier['covariance'][len(h)-1]),0)
            check('filtered_theoretical_coordinate_power',model['filtered_theoretical_power'],np.diag(old['refilter_gain_covariance'][len(old['refilter_gain_covariance'])//2]),0)
            assert len(row['records'])==3 and row['frames_per_block']==len(tile)*480
            for record,(cs,gs) in zip(row['records'],SEEDS):
                assert record['carrier_seed']==cs and record['gain_seed']==gs and record['frames']==frames and record['warmup_frames']==warm
                white=np.random.default_rng(cs).standard_normal((frames+warm+len(h)-1,4))
                c=np.column_stack([sum(signal.fftconvolve(white[:,j],h[:,i,j],mode='full')[len(h)-1:len(h)-1+frames+warm] for j in range(4)) for i in range(4)])
                gain=gain_sequence(old['L'],float(old['parameters'][-1]),frames+warm,gs);full=c*gain;raw=full[warm:]
                filtered=np.column_stack([signal.fftconvolve(full[:,i],q[:,i],mode='full')[:len(full)] for i in range(4)])[warm:]
                check('gain_squared_mean',np.mean(gain[warm:]**2,axis=0),record['gain_squared_mean'],1e-10)
                assert sha(a.input/record['observation_file'])==record['observation_sha256']
                with np.load(a.input/record['observation_file']) as observed:
                    for stage,values,P in [('raw',raw,model['theoretical_power']),('refilter',filtered,model['filtered_theoretical_power'])]:
                        entry=record['files'][stage];assert sha(a.input/entry['file'])==entry['sha256'];saved=np.load(a.input/entry['file'],mmap_mode='r')
                        check('complete_'+stage+'_native_output',values,saved,1e-10,True);check(stage+'_peak',abs(values).max(),record[stage+'_peak'],1e-10,True)
                        pooled=np.zeros((6001,4,4),complex)
                        for block in range(8):
                            samples=saved[block*len(tile)*480:(block+1)*len(tile)*480];actual=energy(samples,tile,P)
                            for key in ['power','power_mean','signed_lagged','theoretical_normalized','measured_normalized']:
                                check('all_'+stage+'_'+key,actual[key],observed[stage+'_'+key][block],1e-10,True)
                            check('all_lag_counts',actual['lag_counts'],observed[stage+'_lag_counts'],0)
                            pooled+=spectrum(samples)/8;r['blocks']+=1;r['window_CSDs']+=len(observed[stage+'_starts'])
                        check('all_'+stage+'_pooled6001x16_CSD',pooled,observed[stage+'_pooled_spectrum'],1e-10,True)
                        check('all_Welch_starts',np.arange(0,len(tile)*480-12000+1,6000),observed[stage+'_starts'],0)
                del white,c,gain,full,raw,filtered,values,saved
                r['records']+=1;save(a.out/'report.json',r);print(dict(cases=r['cases'],records=r['records'],segment=row['segment'],branch=row['branch'],gain_seed=gs),flush=True)
        r['cases']+=1;save(a.out/'report.json',r)
    assert r['cases']==12 and r['records']==36 and r['blocks']==576 and r['window_CSDs']==16704
    r.update(result='passed',all_full_source_streams_replayed=True,all576signed_observations=True,all_full_pooled_CSDs=True,
        old_parameters_unchanged=True,post_refilter_fourth_moment_not_qualified=True,statistical_mean_agreement_not_acceptance=True,new_listening_audio=False)
except Exception as exc:r.update(result='failed',error=repr(exc));raise
finally:save(a.out/'report.json',r)
print(r,flush=True)
