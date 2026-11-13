"""All-origin OA + full even-tensor contractions and independent SVD feasibility."""
import argparse
import itertools
import math
import shutil
import sys
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__)
for key in ['workspace','input','out']:p.add_argument('--'+key,type=Path,required=True)
a=p.parse_args();repo=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(a.workspace/'tools/python_deps'))
import numpy as np
from scipy import signal,linalg,special
from research_archive_v1 import load,save,sha

PAIRS=[(b,c) for b in range(4) for c in range(b,4)]
PERMUTATIONS=[sorted(set(itertools.permutations((i,i,j,j)))) for i,j in PAIRS]


def tensor_operator(K):
    result=np.zeros((len(K),10,10))
    for row,(b,c) in enumerate(PAIRS):
        for col,permutations in enumerate(PERMUTATIONS):
            for i,j,k,l in permutations:
                result[:,row,col]+=np.einsum('tk,tk,tk,tk->t',K[:,b,i],K[:,b,j],K[:,c,k],K[:,c,l])
    return result


def bounds(K,epsilon):
    norm=np.sqrt(np.sum(K*K,axis=3));result=np.zeros((len(K),10,10))
    def delta(b,i,c,j):
        return norm[:,b,i]*epsilon[c,j]+norm[:,c,j]*epsilon[b,i]+epsilon[b,i]*epsilon[c,j]
    def product_norm(b,i,c,j):return np.sqrt(np.sum((K[:,b,i]*K[:,c,j])**2,axis=1))
    def square_error(b,i,c,j):
        d=delta(b,i,c,j);return 2*product_norm(b,i,c,j)*d+d*d
    for row,(b,c) in enumerate(PAIRS):
        for col,(i,j) in enumerate(PAIRS):
            result[:,row,col]=square_error(b,i,c,j)
            if i!=j:
                result[:,row,col]+=square_error(b,j,c,i)
                di,dj=delta(b,i,c,i),delta(b,j,c,j)
                result[:,row,col]+=4*(product_norm(b,i,c,i)*dj+product_norm(b,j,c,j)*di+di*dj)
    return result


def family(A,d):
    result=A.copy()
    for col,(i,j) in enumerate(PAIRS):
        if i==j:result[...,col]*=d
    return result


def base(main,C):
    m=main.astype(np.longdouble);m-=m.mean(axis=0);C=C.astype(np.longdouble)
    variance=np.mean(m*m+np.diagonal(C,axis1=1,axis2=2),axis=0)
    gaussian=[];denominator=[]
    for b,c in PAIRS:
        x,y=m[:,b],m[:,c];v,w,cc=C[:,b,b],C[:,c,c],C[:,b,c]
        central=np.mean(x*x*y*y+x*x*w+y*y*v+4*x*y*cc+v*w+2*cc*cc)
        covariance=np.mean(x*y+cc)
        gaussian.append(central-variance[b]*variance[c]-2*covariance**2)
        denominator.append(variance[b]*variance[c])
    return np.asarray(gaussian,dtype=float),np.asarray(denominator,dtype=float)


def inverse(A,target,row_scale):
    normalized=A/row_scale[:,None];coordinate=np.sqrt(np.sum(normalized*normalized,axis=0))
    if np.any(coordinate==0):return dict(status='rank_deficient_UNKNOWN')
    U,s,Vh=linalg.svd(normalized/coordinate,full_matrices=False)
    rank=int(np.sum(s>np.finfo(float).eps*10*s[0]))
    if rank<10:return dict(status='rank_deficient_UNKNOWN')
    coefficient=(Vh.T@((U.T@(target/row_scale))/s))/coordinate
    latent=np.zeros((4,4))
    for value,(i,j) in zip(coefficient,PAIRS):latent[i,j]=latent[j,i]=value
    eigen=linalg.eigvalsh(latent);norm=linalg.norm(latent,2);margin=1e-10*norm
    if eigen[0]<-margin:status='latent_indefinite_REJECTED'
    elif latent.min()<-margin:status='negative_entry_REJECTED_for_positive_factors'
    else:
        try:
            W=linalg.cholesky(latent,lower=True)
            status='nonnegative_factor_CERTIFIED' if W.min()>=0 and linalg.norm(W@W.T-latent,2)/norm<=1e-10 else 'nonnegative_factor_UNKNOWN'
        except linalg.LinAlgError:status='Cholesky_UNKNOWN'
    return dict(status=status,latent=latent,eigen=eigen,coefficient=coefficient,condition=float(s[0]/s[-1]))


def known(observed,root):
    maximum=0.
    for name in ['Gaussian_FIR','Poisson_binomial']:
        with np.load(root/'known/stationary'/(name+'.npz')) as z:
            x=z['audio'].astype(np.longdouble);w=z['weights'].astype(np.longdouble)
        mean=w@x;x-=mean;C=x.T@(w[:,None]*x)
        square=x*x;fourth=square.T@(w[:,None]*square)-np.outer(np.diag(C),np.diag(C))-2*C*C
        expected=observed['known']['legacy'][name]['expected']
        expected=np.asarray(expected)
        if expected.ndim==1:fourth=np.array([fourth[b,c] for b,c in PAIRS])
        error=float(abs(fourth-expected).max());assert error<1e-10;maximum=max(maximum,error)
    with np.load(root/'known/nonstationary_tensor.npz') as z:
        K,q,w=z['response'],z['q'],z['weights'];saved=z['operator'];expected=z['expected']
    oracle=tensor_operator(K);assert abs(oracle-saved).max()<1e-12
    scaled=family(oracle,3);assert abs(scaled@np.full(10,3.)-expected).max()<1e-10
    # All finite joint-frame tensor coordinates, including odd terms.
    C=q.T@(w[:,None]*q);tensor=np.empty((4,4,4,4))
    for i,j,k,l in itertools.product(range(4),repeat=4):
        tensor[i,j,k,l]=math.fsum(w*q[:,i]*q[:,j]*q[:,k]*q[:,l])-C[i,j]*C[k,l]-C[i,k]*C[j,l]-C[i,l]*C[j,k]
    for at in range(len(K)):
        for row,(b,c) in enumerate(PAIRS):
            total=math.fsum(tensor[i,j,k,l]*np.sum(K[at,b,i]*K[at,b,j]*K[at,c,k]*K[at,c,l])
                           for i,j,k,l in itertools.product(range(4),repeat=4))
            maximum=max(maximum,abs(total-expected[at,row]));assert abs(total-expected[at,row])<1e-10
    for control in observed['known']['legacy']['inverse_controls']+observed['known']['inverse_controls']:
        result=inverse(np.asarray(control['A']),np.asarray(control['target']),np.ones(10))
        assert result['status']==control['solution']['status']
        if 'latent' in result:assert abs(result['latent']-control['solution']['latent']).max()<1e-10
    return maximum


a.out.mkdir(parents=True,exist_ok=False);shutil.copy2(__file__,a.out/'executed_auditor.py')
r=dict(result='running',maximum_operator_error=0.,maximum_bound_relative_error=0.,maximum_solve_relative_error=0.)
try:
    observed=load(a.input/'report.json');assert observed['result']=='both_actual_POST_joint_families_examined_NO_promotion'
    for name,digest in observed['sources'].items():assert sha(a.input/'exact_sources'/name)==digest
    for path,digest in observed['inputs'].items():assert sha(path)==digest
    for name,digest in observed['parent_manifests'].items():assert sha(a.workspace/'baselines'/name/'manifest.json')==digest
    r['known_error']=known(observed,a.input)
    assert sha(a.input/observed['data_file'])==observed['data_sha256']
    with np.load(a.input/observed['data_file']) as z:data={k:z[k] for k in z.files}
    parent=a.workspace/'baselines/idle_post_budget_v1/evidence/observe1'
    previous=load(parent/'report.json')
    with np.load(parent/'conditional_fields.npz') as z:fields={k:z[k] for k in z.files}
    assert np.array_equal(data['origins'],fields['origins'])
    with np.load(a.workspace/'baselines/idle_wave_budget_v1/evidence/observe2/architecture.npz') as z:
        v,sos,warmup=z['variance'],z['sos'],int(z['warmup'])
    observers=[]
    for b,cascade in enumerate(sos):
        impulse=np.zeros(previous['supports'][b]['length']);impulse[0]=1
        for section in cascade:impulse=signal.lfilter(section[:3],section[3:],impulse)
        observers.append(impulse)
    profile=load(a.workspace/'baselines/fixed_source_profiles_v1/evidence/trial1/F2_tailpipe/profile.json')
    taps=[np.asarray(k['taps'])*k['gain'] for k in profile['kernels'][2:]]
    flat=data['origins'].reshape(-1);epsilon=fields['epsilon'][2:].T
    operator=np.empty((len(flat),10,10))
    for first in range(0,len(flat),32):
        last=min(first+32,len(flat));input_rows=[]
        for i,tap in enumerate(taps):
            rows=[]
            for impulse in observers:
                index=warmup+flat[first:last,None]-np.arange(len(impulse))
                weighted=np.sqrt(v[index,i+2])*impulse
                rows.append(signal.oaconvolve(weighted,tap[None,:],axes=1))
            length=max(x.shape[1] for x in rows)
            input_rows.append(np.stack([np.pad(x,((0,0),(0,length-x.shape[1]))) for x in rows],axis=1))
        K=np.stack(input_rows,axis=2);operator[first:last]=tensor_operator(K)
        actual=data['operator'].reshape(-1,10,10)[first:last]
        difference=float(abs(operator[first:last]-actual).max());assert difference<1e-20
        r['maximum_operator_error']=max(r['maximum_operator_error'],difference)
        bound=bounds(K,epsilon);saved=data['error'].reshape(-1,10,10)[first:last]
        error=float((abs(bound-saved)/np.maximum(abs(bound),1e-300)).max());assert error<1e-10
        r['maximum_bound_relative_error']=max(r['maximum_bound_relative_error'],error)
        if first%256==224:print(dict(stage='independent_all_tensor_origins',completed=last,total=len(flat)),flush=True)
    operator=operator.reshape(data['operator'].shape)
    states=[base(fields['main'][b],fields['covariance'][b]) for b in range(2)]
    for name,row in observed['families'].items():
        d=row['multiplier'];matrix=family(operator.mean(axis=1),d);gaussian,denom=states[0]
        target=fields['sourceQ'][0]*denom-gaussian
        solution=inverse(matrix[0],target,denom);assert solution['status']==row['solution']['status']
        def check_solution(s,saved):
            assert s['status']==saved['status']
            if 'latent' in s:
                error=float((abs(s['latent']-saved['latent'])/np.maximum(abs(s['latent']),1.)).max())
                assert error<1e-9;r['maximum_solve_relative_error']=max(r['maximum_solve_relative_error'],error)
                assert abs(s['eigen']-saved['eigenvalues']).max()<1e-8
        check_solution(solution,row['solution'])
        for b,(g,D) in enumerate(states):
            prediction=(matrix[b]@solution['coefficient']+g)/D
            assert abs(prediction-row['algebraic_predictions_NOT_automatically_generative'][b]).max()<1e-10
        minimum=[]
        for group,saved in enumerate(row['leave_groups']):
            keep=np.arange(1024)//16!=group
            current=[base(fields['main'][b,keep],fields['covariance'][b,keep]) for b in range(2)]
            A=family(operator[:,keep].mean(axis=1),d);g,D=current[0]
            fit=inverse(A[0],fields['sourceQ'][0]*D-g,D);check_solution(fit,saved);minimum.append(fit['eigen'][0])
            for b,(g,D) in enumerate(current):
                prediction=(A[b]@fit['coefficient']+g)/D
                assert abs(prediction-saved['predictions'][b]).max()<1e-10
        minimum=np.asarray(minimum);point=solution['eigen'][0]
        se=np.sqrt(63/64*np.sum((minimum-minimum.mean())**2));radius=special.stdtrit(63,.975)*se
        saved=row['minimum_eigenvalue_time_MC']
        assert abs(se-saved['se'])<1e-8 and abs(np.asarray([point-radius,point+radius])-saved['approx_point95']).max()<1e-8
    r.update(result='all2048_full_tensor_operators_and_both64group_feasibilities_verified',input_report_sha256=sha(a.input/'report.json'),
        all_per_origin_columns_verified=True,full_lag_qualified=False,audio_or_runtime_changed=False)
except Exception as exc:
    r.update(result='failed',error=repr(exc));raise
finally:save(a.out/'report.json',r)
