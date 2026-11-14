"""Independent OU generation, direct carrier correlation, finite observer, all costs and Jacobians."""
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
r=dict(result='running',input_sha256=sha(a.input/'report.json'),errors={},cases=0,trace_evaluations=0,source_available=0)
positions=list(zip(*np.tril_indices(4)));initial=np.array([.15 if i==j else 0 for i,j in positions]+[.025])
lower=np.array([.001 if i==j else -.5 for i,j in positions]+[.003]);upper=np.array([.75 if i==j else .5 for i,j in positions]+[.2])


def check(name,x,y,gate=1e-10,relative=False):
    x=np.asarray(x);y=np.asarray(y);error=float(abs(x-y).max())
    if relative:
        scale=float(max(abs(x).max(),abs(y).max()))
        if scale:error/=scale
    r['errors'][name]=max(error,r['errors'].get(name,0.));assert error<=gate,(name,error,gate)


def unpack(x):
    L=np.zeros((4,4))
    for v,(i,j) in zip(x,positions):L[i,j]=v
    return L,L@L.T,float(x[-1])


def observer(h,tile,size,lags):
    maximum=max(sum(tile==tag)-1 for tag in np.unique(tile));q=np.arange(-maximum,maximum+1);D=np.zeros((len(lags),len(q)));counts=np.zeros(len(lags),int)
    for tag in np.unique(tile):
        n=int(sum(tile==tag))
        for row,lag in enumerate(lags):
            pairs=[(u,u+lag) for u in range(n) if 0<=u+lag<n];counts[row]+=len(pairs)
            for column,offset in enumerate(q):
                # Four terms of the finite group-centering law, explicit scalar counts.
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
    n=len(h);power=np.array([math.fsum(h[:,i]**2) for i in range(4)]);squared=np.zeros((len(native),4,4))
    for i in range(4):
        for j in range(4):
            C=np.correlate(h[:,j],h[:,i],mode='full');select=(native>=1-n)&(native<n)
            squared[select,i,j]=C[native[select]+n-1]**2/(power[i]*power[j])
    return dict(W=W,native_lags=native,squared=squared,D=D,counts=counts)


def prediction(op,x):
    _,Gamma,tau=unpack(x);rho=np.exp(-abs(op['native_lags'])/(48000*tau))
    # Stable algebra distinct from production exp(...)*(1+2R²)-1.
    raw=2*op['squared']+(1+2*op['squared'])*np.expm1(4*rho[:,None,None]*Gamma[None])
    return (op['W']@raw.reshape(len(rho),16)).reshape(-1,4,4)


def verify_case(op,x,target,record,saved_prediction,J):
    predicted=prediction(op,x);check('every_terminal_prediction',predicted,saved_prediction,1e-11)
    L,Gamma,tau=unpack(x);check('parameter_snapshot',x,record['parameters'],0)
    singular=np.linalg.svd(J,compute_uv=False);rank=int(np.linalg.matrix_rank(J));condition=float(singular[0]/singular[-1])
    check('reported_condition',condition,record['condition'],1e-10,True);assert rank==record['rank']
    bound=np.minimum(x-lower,upper-x)<=1e-6;assert np.array_equal(bound,record['bound_mask'])
    assert record['success']==(record['status']>0)
    assert record['available']==bool(record['success'] and not bound.any() and rank==11 and condition<1e8)
    check('every_cost',np.sum((predicted-target)**2)/2,record['cost'],1e-11)
    assert len(record['trace'])==record['nfev'] and np.array_equal(record['trace'][0]['parameters'],initial)
    for row in record['trace']:
        p=np.array(row['parameters']);assert np.all(p>=lower) and np.all(p<=upper)
        residual=prediction(op,p)-target;check('all_trace_costs',np.sum(residual*residual)/2,row['cost'],1e-11);r['trace_evaluations']+=1
    check('initial_cost',record['initial_cost'],record['trace'][0]['cost'],0)
    for k in range(11):
        step=1e-7;plus=x.copy();minus=x.copy();plus[k]+=step;minus[k]-=step
        finite=((prediction(op,plus)-prediction(op,minus))/(2*step)).ravel()
        check('every_Jacobian_column',finite,J[:,k],3e-6,True)
    return Gamma,tau


try:
    run=load(a.input/'report.json');assert run['result']=='all12_joint_positive_gain_fits_terminal'
    for name,digest in run['sources'].items():assert sha(repo/name)==digest==sha(a.input/'exact_sources'/name)
    assert sha(a.input/'known.npz')==run['known_arrays_sha256']
    with np.load(a.input/'known.npz') as f:
        x=f['parameters'];L,Gamma,tau=unpack(x);check('known_L',L,f['L'],0);check('known_Gamma',Gamma,f['Gamma'],0)
        node,w=roots_hermitenorm(25);z1,z2=np.meshgrid(node,node,indexing='ij');weights=np.outer(w,w)/(2*np.pi)
        for i in range(4):
            for j in range(4):
                for lag in [0,480,2400]:
                    cross=Gamma[i,j]*math.exp(-abs(lag)/(48000*tau));a0=math.sqrt(Gamma[i,i]);u=a0*z1
                    v=cross/a0*z1+math.sqrt(max(0,Gamma[j,j]-cross**2/Gamma[i,i]))*z2
                    gi=np.exp(u-Gamma[i,i]);gj=np.exp(v-Gamma[j,j])
                    check('independent_gain_fourth',math.fsum((weights*gi*gi*gj*gj).ravel()),math.exp(4*cross),1e-12)
                    check('independent_gain_second',math.fsum((weights*gi*gj).ravel()),math.exp(cross-(Gamma[i,i]+Gamma[j,j])/2),1e-12)
        small=observer(f['small_impulse'],f['small_tile'],3,f['small_lags']);check('small_W',small['W'],f['small_W'],1e-12)
        check('small_explicit_expected',prediction(small,x),f['small_expected'],1e-12)
        op=observer(f['impulse'],f['tile'],480,np.arange(-5,6));check('known_native_W',op['W'],f['native_W'],1e-12)
        check('known_native_carrier_squared',op['squared'],f['carrier_squared'],1e-11)
        check('known_native_target',prediction(op,x),f['target'],1e-11)
        result=run['known']['known_fit'];verify_case(op,np.array(result['parameters']),f['target'],result,f['prediction'],f['J'])
        recovery=float(abs(np.array(result['parameters'])-x).max());check('known_recovery',recovery,run['known']['known_recovery_error'],0);assert recovery<1e-6 and result['available']
        rng=np.random.default_rng(149921);check('known_initial',L@rng.standard_normal(4),f['initial'],0)
        white=rng.standard_normal(f['white'].shape);check('known_white',white,f['white'],0)
        rate=1/(48000*tau);rho=math.exp(-rate);b=math.sqrt(2*math.exp(-rate)*math.sinh(rate));state=f['initial'].copy();latent=np.empty_like(white)
        for k in range(len(white)):state=rho*state+b*(L@white[k]);latent[k]=state
        check('complete_known_latent',latent,f['latent'],1e-10);gain=np.exp(latent-np.diag(Gamma));check('complete_known_gain',gain,f['gain'],1e-10)
        carrier_white=np.random.default_rng(277139).standard_normal(len(white)+8192);check('known_carrier_white',carrier_white,f['carrier_white'],0)
        n=1<<int(math.ceil(math.log2(len(carrier_white)+131072)));z=np.exp(-2j*np.pi*np.arange(n//2+1)/n);F=np.fft.rfft(carrier_white,n=n);carriers=[]
        for sections in f['sos']:
            H=np.ones(len(z),complex)
            for b0,b1,b2,a0,a1,a2 in sections:H*=(b0+b1*z+b2*z*z)/(a0+a1*z+a2*z*z)
            y=np.fft.irfft(F*H,n=n)[8192:8192+len(white)];carriers.extend([y,y])
        carrier=np.column_stack(carriers);check('complete_known_carrier',carrier,f['carrier'],1e-10);check('complete_known_output',carrier*gain,f['output'],1e-10)
        check('finite_gain_second_means',np.mean(gain**2,axis=0),run['known']['finite8s_gain_squared_mean'],1e-11)
        check('finite_output_power',np.mean((carrier*gain)**2,axis=0),run['known']['finite8s_output_power'],1e-11)
    # Known qualification finished; now all real/phase-control terminal and intermediate costs.
    parent=a.workspace/'baselines/accel_upper_forward_v1';assert sha(parent/'manifest.json')==run['parent_manifest_sha256']
    table={v['path']:v['sha256'] for v in load(parent/'manifest.json')['files']}
    for name,digest in run['parent_files'].items():assert sha(parent/name)==digest==table[name]
    for row in run['observations']:
        path=a.input/row['file'];assert sha(path)==row['sha256']
        with np.load(path) as f,np.load(parent/row['parent_file']) as old:
            check('parent_impulse',f['impulse'],old['impulse'],0);check('parent_tile',f['tile'],old['tile'],0);check('parent_target',f['target'],old['observed'],0)
            check('initial_snapshot',f['initial'],initial,0);check('lower_snapshot',f['lower'],lower,0);check('upper_snapshot',f['upper'],upper,0)
            op=observer(f['impulse'],f['tile'],480,np.arange(-5,6));check('all_native_W',op['W'],f['W'],1e-12)
            check('all_native_lags',op['native_lags'],f['native_lags'],0);check('all_carrier_squared',op['squared'],f['carrier_squared'],1e-11)
            check('all_group_coefficients',op['D'],f['window_to_within'],1e-12);check('all_counts',op['counts'],f['counts'],0)
            check('old_Gaussian_bypass',prediction(op,np.r_[np.zeros(10),.025]),old['gaussian'],1e-11)
            Gamma,tau=verify_case(op,f['parameters'],f['target'],row['fit'],f['prediction'],f['J'])
            L,_,_=unpack(f['parameters']);check('all_L',L,f['L'],0);check('all_Gamma',Gamma,f['Gamma'],0)
            check('reported_L',L,row['L'],0);check('reported_Gamma',Gamma,row['Gamma'],0);check('reported_tau',tau,row['tau_seconds'],0)
            check('maximum_error',float(abs(f['prediction']-f['target']).max()),row['maximum_error'],0)
        r['cases']+=1;r['source_available']+=int(row['branch']=='original' and row['fit']['available']);save(a.out/'report.json',r)
        print(dict(cases=r['cases'],segment=row['segment'],branch=row['branch']),flush=True)
    assert r['cases']==12
    r.update(result='passed',all_known_native_arrays=True,all_trace_costs=True,all176x11_Jacobians=True,
             old_phase_audit_hash_reused=True,new_listening_audio=False,numerical_available_not_voice=True)
except Exception as exc:r.update(result='failed',error=repr(exc));raise
finally:save(a.out/'report.json',r)
print(r,flush=True)
