"""Independent gain histories, full convolution contractions and all conditional-mean decompositions."""
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
r=dict(result='running',input_sha256=sha(a.input/'report.json'),errors={},cases=0,blocks=0,native_window_quadratics=0)


def check(name,x,y,gate=1e-10,relative=False):
    x=np.asarray(x);y=np.asarray(y);error=float(abs(x-y).max())
    if relative:
        scale=float(max(abs(x).max(),abs(y).max()))
        if scale:error/=scale
    r['errors'][name]=max(error,r['errors'].get(name,0.));assert error<=gate,(name,error,gate)


def full_contraction(x,k):
    n=x.shape[1];count=min(n,len(k));C=signal.fftconvolve(x,x[:,::-1],mode='full',axes=1)
    return C[:,n-1]*k[0]+C[:,n:n+count-1]@k[1:count]+C[:,n-count:n-1]@k[1:count][::-1]


def reference(g,R,tile,size):
    P=R[0];q=g*g;windows=q.reshape(len(tile),size,4);mean=windows.sum(axis=1)/size;centered=mean.copy()
    for tag in np.unique(tile):
        kk=np.flatnonzero(tile==tag);local=np.array([math.fsum(mean[kk,i])/len(kk) for i in range(4)]);centered[kk]-=local
    path=np.array([math.fsum(centered[:,i]**2)/len(tile) for i in range(4)]);window=np.zeros(4);correction=np.zeros(4)
    for i in range(4):
        K=R[:,i]**2/P[i]**2;window[i]=math.fsum(full_contraction(windows[:,:,i],K))
        for tag in np.unique(tile):
            kk=np.flatnonzero(tile==tag);vector=q[kk[0]*size:(kk[-1]+1)*size,i][None]
            correction[i]+=full_contraction(vector,K)[0]/len(kk)
    carrier=2*(window-correction)/(len(tile)*size**2)
    return dict(path=path,carrier=carrier,total=path+carrier,window_quadratic=window,group_correction=correction)


def gain_sequence(L,tau,frames,seed):
    rng=np.random.default_rng(seed);state=L@rng.standard_normal(4);white=rng.standard_normal((frames,4));rate=1/(48000*tau)
    b=math.sqrt(2*math.exp(-rate)*math.sinh(rate));innov=(white@L.T)*b;latent=np.empty_like(white)
    for start in range(0,frames,512):
        stop=min(start+512,frames);weight=np.exp(-np.arange(1,stop-start+1)*rate)
        latent[start:stop]=weight[:,None]*(state[None]+np.cumsum(innov[start:stop]/weight[:,None],axis=0));state=latent[stop-1]
    return np.exp(latent-np.diag(L@L.T))


try:
    run=load(a.input/'report.json');assert run['result']=='all12_fixed_gain_conditional_means_complete'
    for name,digest in run['sources'].items():assert sha(repo/name)==digest==sha(a.input/'exact_sources'/name)
    assert sha(a.input/'known.npz')==run['known_sha256']
    with np.load(a.input/'known.npz') as f:
        h=f['impulse'];g=f['gain'];tile=f['tile'];R=f['covariance'];N=len(g);size=3;cov=np.zeros((N,N,4))
        for u in range(N):
            for v in range(N):
                lag=abs(v-u)
                if lag<len(R):cov[u,v]=R[lag]*g[u]*g[v]
        E=np.zeros((len(tile),len(tile),4));P=R[0]
        for u in range(len(tile)):
            for v in range(len(tile)):
                a0=slice(u*size,(u+1)*size);b0=slice(v*size,(v+1)*size)
                mean_u=np.diagonal(cov[a0,a0],axis1=0,axis2=1).sum(axis=1)/(size*P)
                mean_v=np.diagonal(cov[b0,b0],axis1=0,axis2=1).sum(axis=1)/(size*P)
                E[u,v]=mean_u*mean_v+2*np.sum(cov[a0,b0]**2,axis=(0,1))/(size**2*P**2)
        A=np.eye(len(tile))
        for tag in np.unique(tile):
            kk=np.flatnonzero(tile==tag);A[np.ix_(kk,kk)]-=1/len(kk)
        expected=np.einsum('uv,uvi->i',A,E)/len(tile);check('known_full_sample_covariance',expected,f['total'],1e-12)
        ref=reference(g,R,tile,size)
        for key in ref:check('known_'+key,ref[key],f[key],1e-12)
    parent=a.workspace/'baselines/accel_upper_realization_v1';assert sha(parent/'manifest.json')==run['parent_manifest_sha256'];table={v['path']:v['sha256'] for v in load(parent/'manifest.json')['files']}
    for name,digest in run['parent_files'].items():assert sha(parent/name)==digest==table[name]
    for row in run['observations']:
        path=a.input/row['file'];assert sha(path)==row['sha256']
        with np.load(path) as f,np.load(parent/row['model_parent_file']) as model,np.load(parent/row['carrier_parent_file']) as c:
            h=c['impulse'];n=len(h);R=np.column_stack([sum(signal.correlate(h[:,i,j],h[:,i,j],mode='full',method='fft')[n-1:] for j in range(4)) for i in range(4)])
            check('all_positive_carrier_covariance',R,c['covariance'][n-1:][:,[0,1,2,3],[0,1,2,3]],1e-10,True)
            check('all_power',f['power'],R[0],1e-10,True);check('tile_unchanged',f['tile'],model['tile'],0)
            expected=model['prediction'][5].diagonal();check('unconditional_prediction_unchanged',expected,f['expected'],0);check('source_target_unchanged',f['source_target'],model['target'][5].diagonal(),0)
            actual=[];conditional=[]
            for seed_index,record in enumerate(row['records']):
                warm=record['warmup_frames'];gain=gain_sequence(model['L'],float(model['parameters'][-1]),record['frames']+warm,record['gain_seed'])[warm:]
                check('all_old_gain_squared_means',np.mean(gain**2,axis=0),record['gain_squared_mean'],1e-10)
                check('all_saved_gain_squared_means',np.mean(gain**2,axis=0),f['squared_gain_means'][seed_index],1e-10)
                for block in range(8):
                    frames=len(f['tile'])*480;ref=reference(gain[block*frames:(block+1)*frames],R,f['tile'],480)
                    for key,mapped in [('path','path'),('carrier','carrier'),('total','conditional'),('window_quadratic','window_quadratic'),('group_correction','group_correction')]:
                        check('all_'+key,ref[key],f[mapped][seed_index,block],1e-10,True)
                    r['blocks']+=1;r['native_window_quadratics']+=len(f['tile'])*4
                old=parent/'evidence/generate1'/record['observation_file'];assert sha(old)==record['observation_sha256']
                with np.load(old) as obs:actual.append(obs['raw_theoretical_normalized'][:,5].diagonal(axis1=1,axis2=2))
            actual=np.array(actual);check('all_original_actual_statistics',actual,f['actual'],0)
            check('all_conditional_sum',f['path']+f['carrier'],f['conditional'],1e-12)
            check('all_gain_path_effect',f['conditional']-expected,f['gain_path_effect'],1e-12);check('all_carrier_realization_effect',actual-f['conditional'],f['carrier_realization_effect'],1e-12)
            check('all_total_effect',actual-expected,f['total_effect'],1e-12);check('all_signed_decomposition',f['gain_path_effect']+f['carrier_realization_effect'],f['total_effect'],1e-12)
            for key,value in [('actual_mean',actual),('conditional_mean',f['conditional']),('mean_gain_path_effect',f['gain_path_effect']),('mean_carrier_realization_effect',f['carrier_realization_effect'])]:check('reported_'+key,np.mean(value,axis=(0,1)),row[key],1e-12)
        r['cases']+=1;save(a.out/'report.json',r);print(dict(cases=r['cases'],segment=row['segment'],branch=row['branch']),flush=True)
    assert r['cases']==12 and r['blocks']==288 and r['native_window_quadratics']==437760
    r.update(result='passed',all1152coordinate_blocks=True,all_existing_gain_histories=True,all_conditional_means_and_decompositions=True,
        conditional_mean_not_VarS_qualification=True,only_pre_refilter_zero_lag_diagonal=True,new_audio=False)
except Exception as exc:r.update(result='failed',error=repr(exc));raise
finally:save(a.out/'report.json',r)
print(r,flush=True)
