"""Independent quadrature, direct FIR correlations, rectangular sums and explicit group operators."""
import argparse,itertools,math,os,shutil,sys
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__)
for key in ['workspace','input','out']:p.add_argument('--'+key,type=Path,required=True)
a=p.parse_args();repo=Path(__file__).resolve().parents[1];sys.path.insert(0,str(a.workspace/'tools/python_deps'))
for key in ['OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','OMP_NUM_THREADS']:os.environ[key]='2'
import numpy as np
from scipy.special import roots_hermitenorm
from research_archive_v1 import load,save,sha
a.out.mkdir(parents=True,exist_ok=False);shutil.copy2(__file__,a.out/'executed_auditor.py')
r=dict(result='running',input_sha256=sha(a.input/'report.json'),errors={},observations=0,pairs=0)


def check(name,x,y,gate=1e-11):
    error=float(abs(np.asarray(x)-np.asarray(y)).max());r['errors'][name]=max(error,r['errors'].get(name,0.));assert error<=gate,(name,error,gate)


def quadrature(h,lag,p):
    node,w=roots_hermitenorm(5);node=np.r_[0,node/np.sqrt(p)];w=np.r_[1-p,w*p/np.sqrt(2*np.pi)]
    times=sorted(set([0,-1,lag,lag-1]));ix=np.array(list(itertools.product(range(6),repeat=len(times))))
    v=node[ix];weight=np.prod(w[ix],axis=1)
    x=v[:,times.index(0)]*h[0,0]+v[:,times.index(-1)]*h[1,0]
    y=v[:,times.index(lag)]*h[0,1]+v[:,times.index(lag-1)]*h[1,1]
    second=math.fsum(weight*x*y)
    square=math.fsum(weight*x*x*y*y)-math.fsum(weight*x*x)*math.fsum(weight*y*y)
    return second,square


def raw(impulse):
    length,d=impulse.shape;G=np.zeros((2*length-1,d,d));B=np.zeros_like(G)
    for i in range(d):
        for j in range(d):
            # Direct time sums, no FFT correlation used in this implementation.
            covariance=np.correlate(impulse[:,j],impulse[:,i],mode='full')
            G[:,i,j]=2*covariance**2
            B[:,i,j]=np.correlate(impulse[:,j]**2,impulse[:,i]**2,mode='full')
    return G,B,np.sum(impulse**2,axis=0)


def rectangle(array,size,maxlag):
    length=(len(array)+1)//2;output=[];difference=np.arange(size)[None,:]-np.arange(size)[:,None]
    for lag in range(-maxlag,maxlag+1):
        indices=lag*size+difference+length-1;mask=(indices>=0)&(indices<len(array));values=np.zeros((*indices.shape,*array.shape[1:]))
        values[mask]=array[indices[mask]];output.append(values.sum(axis=(0,1))/size**2)
    return np.array(output)


def center(window,tile,lags):
    d=window.shape[1];maximum=(len(window)-1)//2;output=np.zeros((len(lags),d,d));counts=np.zeros(len(lags),int)
    for tag in np.unique(tile):
        n=int(sum(tile==tag));P=np.eye(n)-np.ones((n,n))/n
        for i in range(d):
            for j in range(d):
                T=np.array([[window[v-u+maximum,i,j] for v in range(n)] for u in range(n)])
                C=P@T@P.T
                for q,lag in enumerate(lags):
                    values=[C[u,u+lag] for u in range(n) if 0<=u+lag<n]
                    output[q,i,j]+=math.fsum(values)
                    if i==j==0:counts[q]+=len(values)
    return output/counts[:,None,None],counts


def fft_impulse(sos):
    n=65536;z=np.exp(-2j*np.pi*np.arange(n//2+1)/n);columns=[]
    for sections in sos:
        H=np.ones(len(z),complex)
        for b0,b1,b2,a0,a1,a2 in sections:H*=(b0+b1*z+b2*z*z)/(a0+a1*z+a2*z*z)
        columns.append(np.fft.irfft(H,n=n)[:8192])
    return np.column_stack(columns)


try:
    run=load(a.input/'report.json');assert run['result']=='all12_shared_iid_forward_probes_complete'
    for name,digest in run['sources'].items():assert sha(repo/name)==digest==sha(a.input/'exact_sources'/name)
    with np.load(a.input/'known.npz') as f:
        h=f['impulse'];G,B,power=raw(h)
        for probability in [1.,.2]:
            for row in f[f'enumerated_p{probability}']:
                lag=int(row[0]);second,squared=quadrature(h,lag,probability)
                check('all_known_enumerated_moments',[second,squared],row[1:],1e-12)
                if abs(lag)<len(h):expect=G[lag+len(h)-1,0,1]+(3/probability-3)*B[lag+len(h)-1,0,1]
                else:expect=0.
                check('known_closed_fourth',squared,expect,1e-12)
        for key,value in [('gaussian',G),('fourth',B)]:
            window=rectangle(value,3,8);check('known_rectangular_'+key,window,f['window_'+key],1e-12)
            within,counts=center(window,f['tile'],f['within_lags']);check('known_finite_group_'+key,within,f['within_'+key],1e-12)
            check('known_counts',counts,f['counts'],0)
        for key in ['enumerated_second_fourth_error','finite_observer_error','independent_stream_cross_error']:assert run['known'][key]<1e-12
    parent=a.workspace/'baselines/accel_upper_joint_v1';assert sha(parent/'manifest.json')==run['parent_manifest_sha256']
    table={x['path']:x['sha256'] for x in load(parent/'manifest.json')['files']}
    for name,digest in run['parent_files'].items():assert sha(parent/name)==digest==table[name]
    original=load(parent/'evidence/observe1/report.json');cache={}
    for row in run['observations']:
        path=a.input/row['file'];assert sha(path)==row['sha256']
        prior=next(v for v in original['observations'] if v['segment']==row['segment'] and v['branch']==row['branch'])
        with np.load(path) as f,np.load(parent/row['parent_file']) as old:
            check('old_tile',f['tile'],old['tile'],0);check('old_SOS',f['sos'],old['sos'],0)
            check('all_original_observed_lags',f['observed'],prior['energy']['normalized_lagged'],0)
            sos=f['sos'];key=sos.tobytes();maxlag=int(max(sum(f['tile']==tag) for tag in np.unique(f['tile'])))-1
            if key not in cache:
                unique=fft_impulse(sos);h=unique[:,[0,0,1,1]]
                # Compute once per exact SOS identity, then compare every stored array separately.
                G,B,power=raw(unique);index=np.array([0,0,1,1]);G=G[:,index,:][:,:,index];B=B[:,index,:][:,:,index]
                cache[key]=dict(impulse=h,gaussian=G,fourth=B,power=power[index])
            base=cache[key];check('native_FFT_IIR_impulse',base['impulse'],f['impulse'],1e-11)
            # Original tail is evaluated from saved causal samples after full independent impulse agreement.
            tail=np.sum(f['impulse'][-1024:]**2,axis=0)/np.sum(f['impulse']**2,axis=0)
            check('tail_fraction',tail,f['tail_fraction'],0);assert max(tail)<1e-24
            check('power_budget',base['power'],f['power'],1e-11)
            predicted={}
            for name in ['gaussian','fourth']:
                window=rectangle(base[name],480,maxlag)
                check('all_native_rectangular_'+name,window,f['window_'+name],1e-11)
                within,counts=center(window,f['tile'],f['lags']);check('all_lag_counts',counts,f['counts'],0)
                within/=np.outer(base['power'],base['power']);check('all_normalized_within_'+name,within,f[name],1e-11);predicted[name]=within
            coefficient=(f['observed'][5]-predicted['gaussian'][5])/predicted['fourth'][5]
            check('all_pair_coefficients',coefficient,f['coefficient'],1e-9)
            assert np.array_equal(coefficient>=0,f['feasible'])
            prediction=predicted['gaussian']+coefficient[None]*predicted['fourth']
            check('all11signed_pair_predictions',prediction,f['prediction'],1e-11)
            check('by_construction_zero_lag',prediction[5],f['observed'][5],1e-12)
            for pair in row['pairs']:
                i,j=pair['indices'];check('report_pair_coefficient',coefficient[i,j],pair['kappa'],1e-9)
                for name,keyname in [('observed_all11','observed'),('prediction_all11','prediction'),('gaussian_all11','gaussian'),('fourth_all11','fourth')]:
                    check('every_report_'+name,pair[name],f[keyname][:,i,j],0)
                assert pair['Bernoulli_Gaussian_available']==bool(coefficient[i,j]>=0)
                expected=3/(coefficient[i,j]+3) if coefficient[i,j]>=0 else None
                if expected is None:assert pair['implied_Bernoulli_probability'] is None
                else:check('every_implied_probability',expected,pair['implied_Bernoulli_probability'],1e-12)
                error=float(abs(prediction[np.arange(11)!=5,i,j]-f['observed'][np.arange(11)!=5,i,j]).max())
                check('all_nonzero_lag_error',error,pair['max_other_lag_error'],1e-11);r['pairs']+=1
        r['observations']+=1;save(a.out/'report.json',r);print(dict(observations=r['observations'],segment=row['segment'],branch=row['branch']),flush=True)
    assert r['observations']==12 and r['pairs']==192
    r.update(result='passed',all11signed_lags=True,all192pair_diagnostics=True,original_phase_audits='hash_reuse_not_rerun',
             source_PSD_fitted=False,multichannel_fit=False,new_audio=False)
except Exception as exc:r.update(result='failed',error=repr(exc));raise
finally:save(a.out/'report.json',r)
print(r,flush=True)
