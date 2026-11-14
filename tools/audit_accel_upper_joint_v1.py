"""Independent FFT IIR filtering, scalar fourth moments and all finite covariance budgets."""
import argparse,math,os,shutil,sys
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__)
for key in ['workspace','input','out']:p.add_argument('--'+key,type=Path,required=True)
a=p.parse_args();repo=Path(__file__).resolve().parents[1];sys.path.insert(0,str(a.workspace/'tools/python_deps'))
for key in ['OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','OMP_NUM_THREADS']:os.environ[key]='2'
import numpy as np
from scipy.special import roots_hermitenorm
from research_archive_v1 import load,save,sha

a.out.mkdir(parents=True,exist_ok=False);shutil.copy2(__file__,a.out/'executed_auditor.py')
r=dict(result='running',input_sha256=sha(a.input/'report.json'),errors={},observations=0,tile_moments=0,phase_controls=0)


def check(key,x,y,gate=1e-10):
    d=float(abs(np.asarray(x)-np.asarray(y)).max());r['errors'][key]=max(d,r['errors'].get(key,0.));assert d<=gate,(key,d,gate)


def moments(x,weights=None):
    n,d=x.shape;w=np.full(n,1/n) if weights is None else weights
    mean=np.array([math.fsum(float(v)*float(q) for v,q in zip(x[:,i],w)) for i in range(d)]);x=x-mean
    # Scalar pair accumulation, including nonzero Gaussian cross correlations.
    second=np.empty((d,d));fourth=np.empty((d,d))
    for i in range(d):
        for j in range(d):
            second[i,j]=math.fsum(float(v)*float(q) for v,q in zip(x[:,i]*x[:,j],w))
            fourth[i,j]=math.fsum(float(v)*float(q) for v,q in zip(x[:,i]**2*x[:,j]**2,w))
    variance=np.diag(second);sq=fourth-np.outer(variance,variance);connected=sq-2*second**2
    return dict(mean=mean,second=second,fourth=fourth,squared_covariance=sq,connected=connected,normalized_connected=connected/np.outer(variance,variance))


def compare_moments(x,row,label,weights=None):
    actual=moments(x,weights)
    for key,value in actual.items():check(label+'_'+key,value,row[key])
    return actual


def transfer(sos,n):
    z=np.exp(-2j*np.pi*np.arange(n//2+1)/n);H=np.ones(len(z),complex)
    for b0,b1,b2,a0,a1,a2 in sos:H*=np.polyval([b2,b1,b0],z)/np.polyval([a2,a1,a0],z)
    return H


def energy(power,tile,row,saved):
    n,d=power.shape;mean=np.array([math.fsum(power[:,j])/n for j in range(d)])
    total=np.cov(power,rowvar=False,bias=True);within=np.zeros((d,d));between=np.zeros((d,d));residual=np.zeros_like(power)
    for index in sorted(set(tile)):
        select=np.flatnonzero(tile==index);x=power[select];local=np.array([math.fsum(x[:,j])/len(x) for j in range(d)])
        cov=np.cov(x,rowvar=False,bias=True);weight=len(x)/n;within+=weight*cov;between+=weight*np.outer(local-mean,local-mean);residual[select]=x-local
        group=next(v for v in row['groups'] if v['tile']==index);assert group['windows']==len(x)
        check('group_mean',local,group['mean']);check('group_covariance',cov,group['covariance'])
    scale=np.outer(mean,mean)
    for key,value in [('mean',mean),('total',total),('within',within),('between',between),
        ('normalized_total',total/scale),('normalized_within',within/scale),('normalized_between',between/scale)]:check('energy_'+key,value,row[key])
    check('energy_identity',total,within+between);check('energy_residual',residual,saved)
    for k,lag in enumerate(range(-5,6)):
        indices=[(j,j+lag) for j in range(n) if 0<=j+lag<n and tile[j]==tile[j+lag]];assert row['lag_counts'][k]==len(indices) and row['lags_ms'][k]==lag*10
        lagged=np.array([[math.fsum(float(residual[j,i])*float(residual[q,h]) for j,q in indices)/len(indices) for h in range(d)] for i in range(d)])
        check('all_signed_lagged',lagged,row['lagged'][k]);check('all_normalized_signed_lagged',lagged/scale,row['normalized_lagged'][k])


try:
    run=load(a.input/'report.json');assert run['result']=='all12_joint_upper_observations_complete'
    for path,digest in run['sources'].items():assert sha(repo/path)==digest==sha(a.input/'exact_sources'/path)
    # Independent quadrature samples, all scale states and finite unequal groups before source audit.
    with np.load(a.input/'known.npz') as f:
        node,w=roots_hermitenorm(9);z=np.array([[x,y] for x in node for y in node]);q=np.outer(w,w).ravel()/(2*np.pi)
        check('known_gaussian_input',z@np.array([[1.,.6],[0,.8]]),f['gaussian_input']);check('known_weights',q,f['gaussian_weights'])
        G=moments(f['gaussian_input'],f['gaussian_weights']);check('known_Gaussian_connected',G['connected'],0,1e-12);check('known_Gaussian_squared_cov',G['squared_covariance'][0,1],.72,1e-12)
        check('known_shared_input',np.vstack((z/np.sqrt(.2),np.zeros_like(z))),f['shared_input']);check('known_shared_weights',np.r_[q*.2,q*.8],f['shared_weights'])
        xx=[];ww=[]
        for i in [0,1]:
            for j in [0,1]:xx.append(z*np.array([i,j])/np.sqrt(.2));ww.append(q*(.2 if i else .8)*(.2 if j else .8))
        check('known_independent_input',np.concatenate(xx),f['independent_input']);check('known_independent_weights',np.concatenate(ww),f['independent_weights'])
        S=moments(f['shared_input'],f['shared_weights']);I=moments(f['independent_input'],f['independent_weights'])
        check('known_shared_cross',S['normalized_connected'][0,1],4,1e-12);check('known_independent_cross',I['normalized_connected'][0,1],0,1e-12)
        check('known_equal_marginal',np.diag(S['normalized_connected']),np.diag(I['normalized_connected']),1e-12)
        power=f['power'];tile=f['tile'];mean=power.mean(axis=0);total=np.cov(power,rowvar=False,bias=True);parts=np.zeros_like(total)
        for j in range(3):
            x=power[tile==j];local=x.mean(axis=0);parts+=len(x)/len(power)*(np.cov(x,rowvar=False,bias=True)+np.outer(local-mean,local-mean))
        check('known_unequal_group_law',total,parts,1e-12);assert total[0,1]<0
    parent=a.workspace/'baselines/accel_upper_inventory_v1';assert sha(parent/'manifest.json')==run['parent_manifest_sha256']
    table={v['path']:v['sha256'] for v in load(parent/'manifest.json')['files']}
    for name,digest in run['parent_files'].items():assert sha(parent/name)==digest==table[name]
    for row in run['observations']:
        path=a.input/row['file'];assert sha(path)==row['sha256']
        with np.load(path) as f, np.load(parent/row['parent_name']) as old:
            check('parent_exact_audio',f['audio'],old['audio'],0);check('old_left_samples',f['filtered'][:,[0,2]],old['filtered'],0);check('parent_sos',f['sos'],old['sos'],0)
            audio=f['audio'];n=1<<int(math.ceil(math.log2(len(audio)+131072)))
            filtered=np.column_stack([np.fft.irfft(np.fft.rfft(audio[:,ch],n=n)*transfer(sos,n),n=n)[:len(audio)][4800:-4800] for sos in f['sos'] for ch in range(2)])
            check('all4_native_fft_filter',filtered,f['filtered'],1e-11)
            # Audit saved exact native samples after independent waveform agreement.
            filtered=f['filtered'];whole=compare_moments(filtered,row['whole'],'whole')
            tags=np.arange(4800,len(audio)-4800)//12000
            for item in row['tile_moments']:
                x=filtered[tags==item['tile']];assert len(x)==item['frames'];compare_moments(x,item['statistics'],'all192_tile');r['tile_moments']+=1
            count=len(filtered)//480;power=np.array([[np.dot(filtered[j*480:(j+1)*480,k],filtered[j*480:(j+1)*480,k])/480 for k in range(4)] for j in range(count)])
            check('all_native_10ms_power',power,f['power']);tile=(4800+np.arange(count)*480+240)//12000;check('original_tile_tags',tile,f['tile'],0)
            energy(power,tile,row['energy'],f['energy_residual'])
            if row['branch'].startswith('phase_'):
                source=next(v for v in run['observations'] if v['segment']==row['segment'] and v['branch']=='original')
                with np.load(a.input/source['file']) as source_file:original=source_file['audio']
                fft=np.fft.rfft(original,axis=0);seed=int(row['branch'].split('_')[1]);phase=np.random.default_rng(seed).uniform(-np.pi,np.pi,len(fft));phase[0]=phase[-1]=0
                rotated=np.column_stack([fft[:,ch].real*np.cos(phase)-fft[:,ch].imag*np.sin(phase)+1j*(fft[:,ch].real*np.sin(phase)+fft[:,ch].imag*np.cos(phase)) for ch in range(2)])
                check('all9_phase_audio',np.fft.irfft(rotated,n=len(original),axis=0),audio,1e-12)
                actual=np.fft.rfft(audio,axis=0);scale=max(float(abs(fft).max()),1.);check('all9_full_PSD',abs(actual)/scale,abs(fft)/scale,1e-12)
                cross=fft[:,0]*fft[:,1].conj();scale=max(float(abs(cross).max()),1.);check('all9_full_LR_CSD',actual[:,0]*actual[:,1].conj()/scale,cross/scale,1e-12);r['phase_controls']+=1
        r['observations']+=1;save(a.out/'report.json',r)
        print(dict(observation=r['observations'],segment=row['segment'],branch=row['branch']),flush=True)
    assert r['observations']==12 and r['tile_moments']==192 and r['phase_controls']==9
    r.update(result='passed',all4x4_signed_moments_and_covariances=True,all11signed_lags=True,independent_source_identity=False,new_audio=False)
except Exception as exc:r.update(result='failed',error=repr(exc));raise
finally:save(a.out/'report.json',r)
print(r,flush=True)
