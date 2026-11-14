"""Independent multistream covariance, finite observation, complete known generation and every source fit."""
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
r=dict(result='running',input_sha256=sha(a.input/'report.json'),errors={},cases=0,trace_evaluations=0,source_available=0,control_available=0,band_summaries=0)
positions=list(zip(*np.tril_indices(4)));initial=np.array([.15 if i==j else 0 for i,j in positions]+[.025])
lower=np.array([.001 if i==j else -.5 for i,j in positions]+[.003]);upper=np.array([.75 if i==j else .5 for i,j in positions]+[.2])
M=np.array([[1.,0.,1.,0.],[0.,1.,0.,1.]])


def check(name,x,y,gate=1e-10,relative=False):
    x=np.asarray(x);y=np.asarray(y);error=float(abs(x-y).max())
    if relative:
        scale=float(max(abs(x).max(),abs(y).max()))
        if scale:error/=scale
    r['errors'][name]=max(error,r['errors'].get(name,0.));assert error<=gate,(name,error,gate)


def unpack(x):
    L=np.zeros((4,4))
    for value,(i,j) in zip(x,positions):L[i,j]=value
    return L,L@L.T,float(x[-1])


def direct_cov(h):
    n,d,inputs=h.shape;R=np.empty((2*n-1,d,d))
    for i in range(d):
        for j in range(d):R[:,i,j]=sum(signal.correlate(h[:,j,k],h[:,i,k],mode='full',method='fft') for k in range(inputs))
    for lag in sorted(set([0,1,-1,min(31,n-1),-min(31,n-1),n-1,1-n,min(479,n-1),-min(479,n-1)])):
        left=np.arange(max(0,-lag),min(n,n-lag));right=left+lag
        expected=np.array([[math.fsum(np.dot(h[left,i,k],h[right,j,k]) for k in range(inputs)) for j in range(d)] for i in range(d)])
        check('scalar_matrix_covariance_lags',expected,R[lag+n-1],1e-10)
    return np.arange(1-n,n),R


def observer(h,tile,size,lags):
    maximum=max(sum(tile==tag)-1 for tag in np.unique(tile));q=np.arange(-maximum,maximum+1);D=np.zeros((len(lags),len(q)));counts=np.zeros(len(lags),int)
    for tag in np.unique(tile):
        n=int(sum(tile==tag))
        for row,lag in enumerate(lags):
            pairs=[(u,u+lag) for u in range(n) if 0<=u+lag<n];counts[row]+=len(pairs)
            for column,offset in enumerate(q):
                total=0.
                for u,v in pairs:
                    total+=float(v-u==offset)
                    total-=sum(t-u==offset for t in range(n))/n
                    total-=sum(v-t==offset for t in range(n))/n
                total+=len(pairs)*max(0,n-abs(offset))/n**2;D[row,column]+=total
    D/=counts[:,None];extent=maximum*size+size-1;native=np.arange(-extent,extent+1);W=np.zeros((len(lags),len(native)))
    for row in range(len(lags)):
        for column,offset in enumerate(q):
            for diff in range(1-size,size):W[row,offset*size+diff+extent]+=D[row,column]*(size-abs(diff))/size**2
    support,R=direct_cov(h);power=np.array([math.fsum((h[:,i,:]**2).ravel()) for i in range(4)])
    squared=np.zeros((len(native),4,4));valid=(native>=support[0])&(native<=support[-1]);squared[valid]=R[native[valid]-support[0]]**2/np.outer(power,power)
    return dict(W=W,native_lags=native,squared=squared,D=D,counts=counts),support,R


def prediction(op,x):
    _,G,tau=unpack(x);rho=np.exp(-abs(op['native_lags'])/(48000*tau));base=1+2*op['squared']
    raw=2*op['squared']+base*np.expm1(4*rho[:,None,None]*G[None])
    return (op['W']@raw.reshape(len(rho),16)).reshape(-1,4,4)


def verify_case(op,x,target,record,estimate,J):
    check('every_terminal_prediction',prediction(op,x),estimate,1e-11);check('parameters_snapshot',x,record['parameters'],0)
    singular=np.linalg.svd(J,compute_uv=False);rank=int(np.linalg.matrix_rank(J));condition=float(singular[0]/singular[-1]);check('every_condition',condition,record['condition'],1e-10,True)
    bound=np.minimum(x-lower,upper-x)<=1e-6;assert rank==record['rank'] and np.array_equal(bound,record['bound_mask'])
    assert record['success']==(record['status']>0) and record['available']==bool(record['success'] and not bound.any() and rank==11 and condition<1e8)
    assert len(record['trace'])==record['nfev'] and np.array_equal(record['trace'][0]['parameters'],initial)
    for step in record['trace']:
        v=np.array(step['parameters']);assert np.all(v>=lower) and np.all(v<=upper)
        check('all_trace_costs',np.sum((prediction(op,v)-target)**2)/2,step['cost'],1e-11);r['trace_evaluations']+=1
    check('terminal_cost',np.sum((prediction(op,x)-target)**2)/2,record['cost'],1e-11);check('initial_cost',record['initial_cost'],record['trace'][0]['cost'],0)
    for k in range(11):
        plus=x.copy();minus=x.copy();plus[k]+=1e-7;minus[k]-=1e-7
        finite=((prediction(op,plus)-prediction(op,minus))/(2e-7)).ravel();check('all_Jacobian_columns',finite,J[:,k],3e-6,True)


def welch_expected(lags,R,N=12000):
    w=.5-.5*np.cos(2*np.pi*np.arange(N)/N);norm=np.dot(w,w);ac=signal.correlate(w,w,mode='full',method='direct')
    support=np.arange(1-N,N);T=np.zeros((len(support),4,4));valid=abs(lags)<N;T[lags[valid]+N-1]=R[valid]
    fold=np.zeros((N,4,4));np.add.at(fold,support%N,T*ac[:,None,None]/norm);C=np.fft.fft(fold,axis=0)[:N//2+1]
    rows=signal.convolve(T,np.ones((N,1,1)),mode='valid',method='fft')[::-1];B=np.fft.ifft(rows*w[:,None,None],axis=0);mean=rows.mean(axis=0)/N
    for k,Wk in [(0,N/2),(1,-N/4)]:C[k]+=(-Wk*B[k]-Wk*B[k].conj().T+Wk**2*mean)/norm
    one=np.full(N//2+1,2.);one[[0,-1]]=1;return C*one[:,None,None]/48000


def summary_check(C,rows):
    hz=np.arange(6001)*4;S=np.einsum('ai,fij,bj->fab',M,C,M)
    for entry,(lo,hi) in zip(rows,[(0,4000),(4000,8000),(8000,14000),(14000,24000)]):
        kk=np.flatnonzero((hz>=lo)&((hz<hi) if hi<24000 else (hz<=hi)));P=S[kk][:,[0,1],[0,1]].real
        power=np.array([math.fsum(P[:,i])*4 for i in range(2)]);coordinate=np.array([math.fsum(C[kk,i,i].real)*4 for i in range(4)])
        cross=complex(math.fsum(S[kk,0,1].real),math.fsum(S[kk,0,1].imag))*4;norm=cross/math.sqrt(np.prod(power)) if min(power)>0 else 0j
        valid=[j for j in range(len(kk)) if min(P[j])>0];weight=math.fsum(P[j].sum() for j in valid)
        msc=math.fsum(abs(S[kk[j],0,1])**2/(P[j,0]*P[j,1])*P[j].sum() for j in valid)/weight if weight>0 else 0.
        check('all_stereo_band_powers',power,entry['stereo_power'],1e-10,True);check('all_coordinate_band_powers',coordinate,entry['coordinate_power'],1e-10,True)
        check('all_integrated_LR',[norm.real,norm.imag],entry['integrated_normalized_LR'],1e-10);check('all_weighted_MSC',msc,entry['power_weighted_MSC'],1e-10)
        assert entry['defined_stereo_bins']==len(valid) and entry['total_stereo_bins']==len(kk);r['band_summaries']+=1


try:
    run=load(a.input/'report.json');assert run['result']=='all12_source_carrier_joint_gain_fits_terminal'
    for name,digest in run['sources'].items():assert sha(repo/name)==digest==sha(a.input/'exact_sources'/name)
    assert sha(a.input/'known.npz')==run['known_sha256']
    with np.load(a.input/'known.npz') as f:
        x=f['parameters'];L,G,tau=unpack(x);check('known_L',L,f['L'],0)
        small,_,_=observer(f['small_impulse'],f['small_tile'],3,f['small_lags']);check('known_small_W',small['W'],f['small_W'],1e-12)
        check('known_explicit_prediction',prediction(small,x),f['small_expected'],1e-12)
        op,_,_=observer(f['impulse'],f['tile'],480,np.arange(-5,6));check('known_W',op['W'],f['W'],1e-12);check('known_squared',op['squared'],f['carrier_squared'],1e-11)
        check('known_target',prediction(op,x),f['target'],1e-11);result=run['known']['known_fit']
        verify_case(op,np.array(result['parameters']),f['target'],result,f['prediction'],f['J'])
        recovery=float(abs(np.array(result['parameters'])-x).max());assert recovery<1e-6 and result['available'];check('known_recovery',recovery,run['known']['known_recovery_error'],0)
        rng=np.random.default_rng(149921);state=L@rng.standard_normal(4);check('known_initial',state,f['initial'],0)
        white=rng.standard_normal(f['white'].shape);check('known_white',white,f['white'],0);latent=np.empty_like(white);rate=1/(48000*tau)
        rho=math.exp(-rate);b=math.sqrt(2*math.exp(-rate)*math.sinh(rate))
        for k in range(len(white)):state=rho*state+b*(L@white[k]);latent[k]=state
        gain=np.exp(latent-np.diag(G));check('complete_known_latent',latent,f['latent'],1e-10);check('complete_known_gain',gain,f['gain'],1e-10)
        h=f['impulse'];cw=np.random.default_rng(277139).standard_normal(f['carrier_white'].shape);check('known_carrier_white',cw,f['carrier_white'],0)
        carrier=np.column_stack([sum(signal.fftconvolve(cw[:,q],h[:,i,q],mode='full')[len(h)-1:len(h)-1+len(white)] for q in range(4)) for i in range(4)])
        check('complete_known_carrier',carrier,f['carrier'],1e-10);check('complete_known_output',carrier*gain,f['output'],1e-10)
        for k in [0,1,479,8191,65003,len(white)-1]:
            direct=np.array([sum(np.dot(cw[len(h)-1+k-np.arange(len(h)),q],h[:,i,q]) for q in range(4)) for i in range(4)])
            check('known_scalar_carrier_samples',direct,carrier[k],1e-10)
    parent=a.workspace/'baselines/accel_upper_carrier_v1';assert sha(parent/'manifest.json')==run['parent_manifest_sha256'];table={v['path']:v['sha256'] for v in load(parent/'manifest.json')['files']}
    for name,digest in run['parent_files'].items():assert sha(parent/name)==digest==table[name]
    oldrun=load(parent/'inputs/parents/gain/evidence/fit1/report.json')
    for row,before in zip(run['observations'],oldrun['observations']):
        path=a.input/row['file'];assert sha(path)==row['sha256']
        with np.load(path) as f,np.load(parent/row['carrier_parent_file']) as c,np.load(parent/row['gain_parent_file']) as old:
            check('source_impulse',f['impulse'],c['impulse'],0);check('source_tile',f['tile'],old['tile'],0);check('source_target',f['target'],old['target'],0)
            check('initial_unchanged',f['initial'],initial,0);check('lower_unchanged',f['lower'],lower,0);check('upper_unchanged',f['upper'],upper,0)
            op,lags,R=observer(f['impulse'],f['tile'],480,np.arange(-5,6))
            for name,key in [('W','W'),('native_lags','native_lags'),('squared','carrier_squared'),('D','window_to_within'),('counts','counts')]:check('all_'+name,op[name],f[key],1e-11)
            check('carrier_covariance_independent',R,c['covariance'],1e-10,True)
            verify_case(op,f['parameters'],f['target'],row['fit'],f['prediction'],f['J']);L,G,tau=unpack(f['parameters'])
            check('all_L',L,f['L'],0);check('all_Gamma',G,f['Gamma'],0);check('reported_L',L,row['L'],0);check('reported_Gamma',G,row['Gamma'],0);check('reported_tau',tau,row['tau_seconds'],0)
            check('maximum_error',abs(f['prediction']-f['target']).max(),row['maximum_error'],0)
            check('old_parameters',f['old_parameters'],old['parameters'],0);check('old_white_prediction',f['white_prediction'],old['prediction'],0)
            check('old_white_cost',np.sum((old['prediction']-old['target'])**2)/2,row['old_white_cost'],1e-11)
            fixed=prediction(op,old['parameters']);check('fixed_coloured_prediction',fixed,f['fixed_prediction'],1e-11)
            check('fixed_coloured_cost',np.sum((fixed-old['target'])**2)/2,row['fixed_coloured_cost'],1e-11);assert row['old_fit_available']==before['fit']['available']
            moment=np.exp(G[None]*np.exp(-abs(lags)/(48000*tau))[:,None,None]-(np.diag(G)[:,None]+np.diag(G)[None,:])[None]/2);Rg=R*moment
            check('all_gain_covariance',Rg,f['gain_covariance'],1e-10,True)
            q=c['q'];Rf=np.empty((len(Rg)+2*len(q)-2,4,4))
            for i in range(4):
                for j in range(4):Rf[:,i,j]=signal.fftconvolve(Rg[:,i,j],signal.correlate(q[:,j],q[:,i],mode='full',method='fft'),mode='full')
            ll=np.arange(lags[0]-(len(q)-1),lags[-1]+len(q));check('refilter_lags',ll,f['refilter_lags'],0);check('all_refilter_covariance',Rf,f['refilter_gain_covariance'],1e-10,True)
            for name,ss,rr in [('Welch_gain',lags,Rg),('Welch_refilter_gain',ll,Rf)]:
                spectrum=welch_expected(ss,rr);check('every_full_spectral_matrix_'+name,spectrum,f[name],1e-10,True);summary_check(f[name],row['summaries'][name])
        r['cases']+=1;r['source_available']+=int(row['branch']=='original' and row['fit']['available']);r['control_available']+=int(row['branch']!='original' and row['fit']['available'])
        save(a.out/'report.json',r);print(dict(cases=r['cases'],segment=row['segment'],branch=row['branch']),flush=True)
    assert r['cases']==12 and r['band_summaries']==96
    r.update(result='passed',all_known_native_waveform=True,all_trace_costs=True,all176x11_Jacobians=True,all6001bins16complex_postgain_refilter=True,
        old_fit_rules_unchanged=True,near_null_full_MSC_qualified=False,numeric_availability_not_voice=True,new_listening_audio=False)
except Exception as exc:r.update(result='failed',error=repr(exc));raise
finally:save(a.out/'report.json',r)
print(r,flush=True)
