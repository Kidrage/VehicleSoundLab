"""Independent matrix roots, full complex spectra, linear covariance, Welch and all energy/band budgets."""
import argparse,math,os,shutil,sys
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__)
for key in ['workspace','input','energy','summary','out']:p.add_argument('--'+key,type=Path,required=True)
a=p.parse_args();repo=Path(__file__).resolve().parents[1];sys.path.insert(0,str(a.workspace/'tools/python_deps'))
for key in ['OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','OMP_NUM_THREADS']:os.environ[key]='2'
import numpy as np
from scipy import signal
from research_archive_v1 import load,save,sha
a.out.mkdir(parents=True,exist_ok=False);shutil.copy2(__file__,a.out/'executed_auditor.py')
r=dict(result='running',input_sha256=sha(a.input/'report.json'),energy_sha256=sha(a.energy/'report.json'),
       summary_sha256=sha(a.summary/'report.json'),errors={},cases=0,band_summaries=0,native_windows=0)
M=np.array([[1.,0.,1.,0.],[0.,1.,0.,1.]])


def check(name,x,y,gate=1e-10,relative=False):
    x=np.asarray(x);y=np.asarray(y);error=float(abs(x-y).max())
    if relative:
        scale=float(max(abs(x).max(),abs(y).max()))
        if scale:error/=scale
    r['errors'][name]=max(error,r['errors'].get(name,0.));assert error<=gate,(name,error,gate)


def direct_cov(h):
    n,d,q=h.shape;out=np.empty((2*n-1,d,d))
    for i in range(d):
        for j in range(d):out[:,i,j]=sum(signal.correlate(h[:,j,k],h[:,i,k],mode='full',method='fft') for k in range(q))
    for lag in sorted(set([0,1,-1,min(31,n-1),-min(31,n-1),n-1,1-n,min(479,n-1),-min(479,n-1),min(1200,n-1),-min(1200,n-1)])):
        left=np.arange(max(0,-lag),min(n,n-lag));right=left+lag
        matrix=np.array([[sum(float(np.dot(h[left,i,k],h[right,j,k])) for k in range(q)) for j in range(d)] for i in range(d)])
        check('scalar_native_covariance_lags',matrix,out[lag+n-1],1e-10)
    return np.arange(1-n,n),out


def welch_expected(lags,R,N):
    # Direct time-domain correlation sums cover every aperture pair.
    w=.5-.5*np.cos(2*np.pi*np.arange(N)/N);normal=np.dot(w,w);ac=signal.correlate(w,w,mode='full',method='direct')
    support=np.arange(1-N,N);T=np.zeros((len(support),*R.shape[1:]));valid=abs(lags)<N;T[lags[valid]+N-1]=R[valid]
    weighted=T*ac[:,None,None]/normal;fold=np.zeros((N,*R.shape[1:]));np.add.at(fold,support%N,weighted)
    C=np.fft.fft(fold,axis=0)[:N//2+1]
    row_sums=signal.convolve(T,np.ones((N,1,1)),mode='valid',method='fft')[::-1]
    B=np.fft.ifft(row_sums*w[:,None,None],axis=0);mean_cov=row_sums.mean(axis=0)/N
    for k,Wk in [(0,N/2),(1,-N/4)]:C[k]+=(-Wk*B[k]-Wk*B[k].conj().T+Wk**2*mean_cov)/normal
    one=np.full(N//2+1,2.);one[[0,-1]]=1;return C*one[:,None,None]/48000


def validate_summaries(C,rows,N=12000):
    hz=np.arange(N//2+1)*48000/N;S=np.einsum('ai,fij,bj->fab',M,C,M)
    for row,(lo,hi) in zip(rows,[(0,4000),(4000,8000),(8000,14000),(14000,24000)]):
        indices=np.flatnonzero((hz>=lo)&((hz<hi) if hi<24000 else (hz<=hi)));power=np.array([math.fsum(C[indices,i,i].real)*48000/N for i in range(4)])
        P=np.array([[S[k,0,0].real,S[k,1,1].real] for k in indices]);sp=np.array([math.fsum(P[:,i])*48000/N for i in range(2)])
        cross=complex(math.fsum(S[indices,0,1].real),math.fsum(S[indices,0,1].imag))*48000/N
        norm=cross/math.sqrt(float(np.prod(sp))) if min(sp)>0 else 0j;defined=[j for j in range(len(P)) if min(P[j])>0]
        weight=math.fsum(float(P[j].sum()) for j in defined)
        numerator=math.fsum(float(abs(S[indices[j],0,1])**2/(P[j,0]*P[j,1])*P[j].sum()) for j in defined)
        msc=numerator/weight if weight>0 else 0.
        assert row['band_hz']==[lo,hi] and row['defined_stereo_bins']==len(defined) and row['total_stereo_bins']==len(indices)
        check('all_coordinate_band_power',power,row['coordinate_power'],1e-10,True);check('all_stereo_band_power',sp,row['stereo_power'],1e-10,True)
        check('all_integrated_LR',np.array([norm.real,norm.imag]),row['integrated_normalized_LR'],1e-10);check('all_weighted_MSC',msc,row['power_weighted_MSC'],1e-10)
        r['band_summaries']+=1


try:
    run=load(a.input/'report.json');energy=load(a.energy/'report.json');summary=load(a.summary/'report.json')
    assert run['result']=='all12_source_carriers_and_gain_budgets_complete'
    assert energy['result']=='all12_fixed_gain_carrier_compatibility_diagnosed' and summary['result']=='all12_coherence_summaries_corrected_spectra_unchanged'
    assert energy['input_sha256']==summary['input_sha256']==sha(a.input/'report.json')
    for name,digest in run['sources'].items():
        assert sha(a.input/'exact_sources'/name)==digest
        if name!='tools/accel_upper_carrier_v1/spectral.py':assert sha(repo/name)==digest
    old=(a.input/'exact_sources/tools/accel_upper_carrier_v1/spectral.py').read_text(encoding='utf-8')
    fixed=old.replace('valid=den>0;','valid=(P[:,0]>0)&(P[:,1]>0);').replace('weight=P.sum(axis=1);','weight=np.where(valid,P.sum(axis=1),0.);')
    assert fixed==(repo/'tools/accel_upper_carrier_v1/spectral.py').read_text(encoding='utf-8')
    for stage,folder in [(energy,a.energy),(summary,a.summary)]:
        for name,digest in stage['sources'].items():assert sha(repo/name)==digest==sha(folder/'exact_sources'/name)
    assert sha(a.input/'known.npz')==run['known_sha256']
    with np.load(a.input/'known.npz') as f:
        h=f['impulse'];lags,R=direct_cov(h);check('known_full_covariance',R,f['covariance'],1e-12)
        check('known_detrended_Welch',welch_expected(lags,R,32),f['explicit_Welch'],1e-12)
        H=np.fft.rfft(f['compiled'],n=256,axis=0);one=np.full(129,2.);one[[0,-1]]=1
        C=np.einsum('fiq,fjq->fij',H.conj(),H)*one[:,None,None]/48000;check('known_factor_phase',C,f['target'],1e-12)
        # Direct convolved short FIR, independently verify the diagonal refilter.
        q=f['q'];hh=np.array([[np.convolve(h[:,i,j],q[:,i]) for j in range(4)] for i in range(4)]).transpose(2,0,1)
        ll,rr=direct_cov(hh);check('known_refilter_lags',ll,f['refilter_lags'],0);check('known_refilter_covariance',rr,f['refilter_covariance'],1e-12)
    with np.load(a.summary/'known.npz') as f:
        C=f['spectra'];S=np.einsum('ai,fij,bj->fab',M,C,M);P=S[:,[0,1],[0,1]].real
        assert np.all(P[0]<0) and np.all(P[1]==0) and np.all(P[2]>0) and P[3,0]>0>P[3,1]
        assert np.array_equal(np.flatnonzero(np.all(P>0,axis=1)),[2])
    roots={}
    for key,record in run['parents'].items():
        root=a.workspace/'baselines'/record['stage'];roots[key]=root;assert sha(root/'manifest.json')==record['manifest_sha256']
        table={x['path']:x['sha256'] for x in load(root/'manifest.json')['files']}
        for name,digest in record['files'].items():assert sha(root/name)==digest==table[name]
    for row,er,sr in zip(run['observations'],energy['cases'],summary['observations']):
        assert (row['segment'],row['branch'])==(er['segment'],er['branch'])==(sr['segment'],sr['branch'])
        path=a.input/row['file'];assert sha(path)==row['sha256'] and sha(a.energy/er['file'])==er['sha256']
        with np.load(path) as f,np.load(roots['raw']/row['source_parent_file']) as raw,np.load(roots['gain']/row['gain_parent_file']) as gain:
            audio=raw['filtered'];N=12000;kw=dict(fs=48000,window='hann',nperseg=N,noverlap=N//2,nfft=N,detrend='constant',scaling='density',return_onesided=True)
            C=np.empty((6001,4,4),complex)
            for i in range(4):
                for j in range(4):_,C[:,i,j]=signal.csd(audio[:,i],audio[:,j],**kw)
            check('all_Scipy_complex_CSD',C,f['target'],1e-10,True)
            starts=np.arange(0,len(audio)-N+1,N//2);check('all_window_starts',starts,f['starts'],0);assert row['windows']==len(starts);r['native_windows']+=len(starts)
            one=np.full(6001,2.);one[[0,-1]]=1;T=C*48000/one[:,None,None];U,s,Vh=np.linalg.svd(T)
            root=np.einsum('fik,fk,fjk->fij',U,np.sqrt(s),U.conj());refH=root.conj();storedH=np.fft.rfft(np.roll(f['impulse'],-N//2,axis=0),axis=0)
            check('all_SVD_matrix_roots',refH,storedH,1e-7,True)
            compiled=np.einsum('fiq,fjq->fij',storedH.conj(),storedH)*one[:,None,None]/48000;check('all_compiled_grid',compiled,f['compiled_grid'],1e-10,True)
            h=f['impulse'];lags,R=direct_cov(h);check('all_linear_covariances',R,f['covariance'],1e-10,True);check('all_signed_lags',lags,f['lags'],0)
            Gamma=gain['Gamma'];tau=float(gain['parameters'][-1]);check('frozen_Gamma',Gamma,f['Gamma'],0);check('frozen_tau',tau,f['tau'],0)
            rho=np.exp(-abs(lags)/(48000*tau));A=np.exp(rho[:,None,None]*Gamma-(np.diag(Gamma)[:,None]+np.diag(Gamma)[None,:])/2)
            Rg=R*A;check('all_gain_covariance',Rg,f['gain_covariance'],1e-10,True)
            check('variance_invariant',np.diag(Rg[N-1]),np.diag(R[N-1]),1e-12)
            spectra=dict(target=C,compiled_grid=compiled,Welch_carrier=welch_expected(lags,R,N),Welch_gain=welch_expected(lags,Rg,N))
            P=65536;z=np.exp(-2j*np.pi*np.arange(P)/P);Q=[]
            for sections in f['sos']:
                H=np.ones(P,complex)
                for b0,b1,b2,a0,a1,a2 in sections:H*=(b0+b1*z+b2*z*z)/(a0+a1*z+a2*z*z)
                Q.extend([H,H])
            Q=np.column_stack(Q);extent=20190;ll=np.arange(-extent,extent+1)
            for name,RR in [('carrier',R),('gain',Rg)]:
                buffer=np.zeros((P,4,4));buffer[lags%P]=RR
                Cq=np.fft.fft(buffer,axis=0)*Q.conj()[:,:,None]*Q[:,None,:];period=np.fft.ifft(Cq,axis=0).real
                ref=np.concatenate((period[-extent:],period[:extent+1]));spectra['Welch_refilter_'+name]=welch_expected(ll,ref,N)
            for name,value in spectra.items():
                check('every_full_spectral_matrix_'+name,value,f[name],1e-10,True)
                validate_summaries(f[name],sr['summaries'][name])
            with np.load(a.energy/er['file']) as e:
                native=gain['native_lags'];power=np.diag(R[N-1]);squared=R[native+N-1]**2/np.outer(power,power)
                raw_cov=np.exp(4*Gamma*np.exp(-abs(native)/(48000*tau))[:,None,None])*(1+2*squared)-1
                expected=(gain['W']@raw_cov.reshape(len(native),16)).reshape(11,4,4)
                check('every_fixed_gain_energy_prediction',expected,e['prediction'],1e-10)
                check('energy_target_unchanged',gain['target'],e['target'],0);check('energy_parameters_unchanged',gain['parameters'],e['parameters'],0)
                check('energy_new_cost',np.sum((expected-gain['target'])**2)/2,er['new_cost'],1e-11)
                check('energy_old_cost',np.sum((gain['prediction']-gain['target'])**2)/2,er['previous_cost'],1e-11)
        r['cases']+=1;save(a.out/'report.json',r);print(dict(cases=r['cases'],segment=row['segment'],branch=row['branch']),flush=True)
    assert r['cases']==12 and r['native_windows']==348 and r['band_summaries']==288
    r.update(result='passed',all6001bins_all16complex_entries=True,corrected_summary_only_spectra_preserved=True,
             all12_fixed_gain_energy_compatibility=True,near_null_all_bin_coherence_qualified=False,new_listening_audio=False)
except Exception as exc:r.update(result='failed',error=repr(exc));raise
finally:save(a.out/'report.json',r)
print(r,flush=True)
