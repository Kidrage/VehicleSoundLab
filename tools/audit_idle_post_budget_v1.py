"""Independent POST responses, source moments, raw15partition cumulants and inverse."""
import argparse
import cmath
import itertools
import math
import shutil
import sys
from pathlib import Path
p = argparse.ArgumentParser(description=__doc__)
for key in ['workspace', 'input', 'out']: p.add_argument('--'+key, type=Path, required=True)
a = p.parse_args(); repo = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(a.workspace/'tools/python_deps'))
import numpy as np
from scipy import signal, linalg, special
from research_archive_v1 import load, save, sha

PAIRS = [(b,c) for b in range(4) for c in range(b,4)]; AUTO = [0,4,7,9]
ORDERS = [(1,0),(0,1),(2,0),(0,2),(1,1),(2,1),(1,2),(2,2)]


def partitions(items):
    if not items: yield []; return
    for rest in partitions(items[1:]):
        yield [[items[0]]]+rest
        for i in range(len(rest)): yield [([items[0]]+x if j == i else x) for j,x in enumerate(rest)]


PARTITIONS = list(partitions([0,1,2,3]))


def cumulant(raw):
    table = {(0,0):1., **dict(zip(ORDERS,raw))}; products = []
    for blocks in PARTITIONS:
        value = (-1)**(len(blocks)-1)*math.factorial(len(blocks)-1)
        for block in blocks:
            x = sum(i < 2 for i in block); value *= table[x,len(block)-x]
        products.append(value)
    return math.fsum(products)


def gaussian_raw(m,n,v,w,c,j):
    return np.array([m.mean(),n.mean(),np.mean(m*m+v),np.mean(n*n+w),np.mean(m*n+c),
        np.mean(m*m*n+n*v+2*m*c),np.mean(m*n*n+m*w+2*n*c),
        np.mean(m*m*n*n+m*m*w+n*n*v+4*m*n*c+v*w+2*c*c+j)])


def known():
    origins = np.arange(3,11); t = np.arange(12)
    g = np.column_stack([1+.3*np.sin(.9*t),.8+.2*np.cos(.4*t)])
    taps = [[.7,-.2],[.3,.6]]; obs = [[.8,.3],[-.25,.5]]
    main = np.column_stack([.1+.2*np.cos(origins*.31),-.04+.15*np.sin(origins*.59)])
    error = 0.
    for levels, probabilities, kappa in [([-1.,1.],[.5,.5],-2.),
        ([-np.sqrt(3),0.,np.sqrt(3)],[1/6,2/3,1/6],0.),
        ([-np.sqrt(6),0.,np.sqrt(6)],[1/12,5/6,1/12],3.)]:
        raw = np.zeros((3,8)); theory = np.zeros_like(raw)
        for index,n in enumerate(origins):
            H = np.zeros((2,2,3))
            for b,u,i,k in itertools.product(range(2),repeat=4): H[b,i,u+k] += obs[b][u]*g[n-u,i]*taps[i][k]
            C = np.einsum('bik,cik->bc',H,H); A = np.einsum('bik,cik->bc',H*H,H*H)
            draws = np.array(list(itertools.product(range(len(levels)),repeat=6)))
            weights = np.prod(np.asarray(probabilities)[draws],axis=1)
            values = np.asarray(levels)[draws].reshape(-1,2,3)
            output = main[index]+np.einsum('sik,bik->sb',values,H)
            for pair,(b,c) in enumerate([(0,0),(0,1),(1,1)]):
                x,y = output[:,b],output[:,c]
                raw[pair] += [weights@(x**p*y**q)/len(origins) for p,q in ORDERS]
                theory[pair] += gaussian_raw(*[np.asarray([value]) for value in [main[index,b],main[index,c],C[b,b],C[c,c],C[b,c],kappa*A[b,c]]])/len(origins)
        error = max(error,float(abs(raw-theory).max()),max(abs(cumulant(x)-cumulant(y)) for x,y in zip(raw,theory)))
    assert error < 1e-12
    return error


def support(cascade):
    sections=[]; polemax=0.
    for b0,b1,b2,a0,a1,a2 in cascade:
        d=cmath.sqrt(complex(a1*a1-4*a0*a2)); p1=(-a1+d)/(2*a0); p2=(-a1-d)/(2*a0)
        assert abs(p1-p2)>1e-10 and max(abs(p1),abs(p2))<1
        h0=b0/a0;h1=(b1-a1*h0)/a0;h2=(b2-a1*h1-a2*h0)/a0;h3=(-a1*h2-a2*h1)/a0
        A=(h3-p2*h2)/(p1-p2);B=(p1*h2-h3)/(p1-p2);r=max(abs(p1),abs(p2))
        sections.append((h0,h1,abs(A)+abs(B),r));polemax=max(polemax,r)
    R=polemax**-.5;weighted=math.prod(abs(h0)+R*abs(h1)+R*R*c/(1-R*r) for h0,h1,c,r in sections)
    length=max(2,math.ceil(math.log(weighted/1e-13)/math.log(R)));bound=weighted*R**(-length)
    delta=np.zeros(length);delta[0]=1
    for section in cascade:delta=signal.lfilter(section[:3],section[3:],delta)
    return delta,dict(length=length,R=R,weighted_norm=weighted,tail_L1_bound=bound)


def state(m,C,A):
    m=m.astype(np.longdouble);C=C.astype(np.longdouble);A=A.astype(np.longdouble)
    variance=np.mean((m-m.mean(axis=0))**2,axis=0)+np.diag(C.mean(axis=0));denom=[];K=[];terms=[]
    def cov(x,y):return np.mean(x*y)-x.mean()*y.mean()
    for b,c in PAIRS:
        x,y=m[:,b],m[:,c];v,w,cc=C[:,b,b],C[:,c,c],C[:,b,c]
        raw=gaussian_raw(x,y,v,w,cc,np.zeros(len(m)));K.append(cumulant(raw))
        x=x-x.mean();y=y-y.mean()
        terms.append([np.mean(x*x*y*y)-np.mean(x*x)*np.mean(y*y)-2*np.mean(x*y)**2,
            cov(v,w),2*cov(cc,cc),cov(x*x,w),cov(y*y,v),4*cov(x*y,cc),0.])
        denom.append(variance[b]*variance[c])
    return dict(variance=np.asarray(variance,dtype=float),gaussian=np.asarray(K,dtype=float),terms=np.asarray(terms,dtype=float),
                denominator=np.asarray(denom,dtype=float),operator=np.asarray([A[:,b,c].mean(axis=0) for b,c in PAIRS],dtype=float),
                mean_power=np.asarray((m*m).mean(axis=0)+np.diag(C.mean(axis=0)),dtype=float))


def solve(s,q):
    A=s['operator'][AUTO]/s['denominator'][AUTO,None]
    y=q[AUTO]-s['gaussian'][AUTO]/s['denominator'][AUTO]
    coordinate=np.sqrt(np.sum(A*A,axis=0));singular=linalg.svdvals(A/coordinate)
    rank=np.sum(singular>np.finfo(float).eps*4*singular[0]);assert rank==4
    return linalg.solve(A/coordinate,y)/coordinate


def predict(s,k):return (s['gaussian']+s['operator']@k)/s['denominator']


a.out.mkdir(parents=True,exist_ok=False);shutil.copy2(__file__,a.out/'executed_auditor.py')
r=dict(result='running',known_error=0.,maximum_C_error=0.,maximum_A_error=0.,maximum_normalized_budget_error=0.)
try:
    observed=load(a.input/'report.json');assert observed['result']=='all_POST_zero_budgets_and_TRAIN_allocation_complete_NO_promotion'
    for name,digest in observed['sources'].items():assert sha(a.input/'exact_sources'/name)==digest
    for path,digest in observed['inputs'].items():assert sha(path)==digest
    for name,digest in observed['parent_manifests'].items():assert sha(a.workspace/'baselines'/name/'manifest.json')==digest
    r['known_error']=known()
    assert sha(a.input/observed['data_file'])==observed['data_sha256']
    with np.load(a.input/observed['data_file']) as archive:data={k:archive[k] for k in archive.files}
    rng=np.random.Generator(np.random.PCG64(20261114))
    origins=rng.integers(0,134400,size=(2,64,16))+4800+np.arange(2)[:,None,None]*144000
    assert np.array_equal(origins,data['origins']);flat=origins.reshape(-1)
    profile=load(a.workspace/'baselines/fixed_source_profiles_v1/evidence/trial1/F2_tailpipe/profile.json')
    with np.load(a.workspace/'baselines/idle_wave_budget_v1/evidence/observe2/architecture.npz') as archive:
        v,sos,h,main=archive['variance'],archive['sos'],archive['h'],archive['main'];warmup=int(archive['warmup'])
    observers=[]
    for b,cascade in enumerate(sos):
        impulse,description=support(cascade);observers.append(impulse)
        for key,value in description.items():
            relative=abs(value-observed['supports'][b][key])/max(abs(value),1e-300)
            assert relative<1e-10,(b,key,relative)
    assert np.array_equal(main[flat].reshape(2,1024,4),data['main'])
    covariance=np.zeros((len(flat),4,4));operator=np.zeros((len(flat),4,4,4))
    bound2=np.zeros((6,4,4));bound4=np.zeros_like(bound2)
    law=load(a.workspace/'baselines/idle_positive_power_v1/evidence/observe1/report.json')['observations'][0]['models']['expanded']
    gmax=np.r_[np.ones(2),np.sqrt(law['bounds']['power_upper'])];assert np.array_equal(gmax,data['global_gmax'])
    for i,kernel in enumerate(profile['kernels']):
        tap=np.asarray(kernel['taps'])*kernel['gain'];amplitude=np.sqrt(v[:,i])
        epsilon=np.array([gmax[i]*math.fsum(abs(tap))*d['tail_L1_bound'] for d in observed['supports']])
        assert np.allclose(epsilon,data['epsilon'][i],rtol=1e-12,atol=0.)
        for first in range(0,len(flat),64):
            last=min(first+64,len(flat));rows=[]
            for impulse in observers:
                addresses=warmup+flat[first:last,None]-np.arange(len(impulse))
                weighted=amplitude[addresses]*impulse
                rows.append(signal.oaconvolve(weighted,tap[None,:],axes=1))
            length=max(x.shape[1] for x in rows)
            K=np.stack([np.pad(x,((0,0),(0,length-x.shape[1]))) for x in rows],axis=1)
            C=np.einsum('tbk,tck->tbc',K,K);A=np.einsum('tbk,tck->tbc',K*K,K*K)
            covariance[first:last]+=C
            if i>=2:operator[first:last,:,:,i-2]=A
            norm=np.linalg.norm(K,axis=2)
            e=norm[:,:,None]*epsilon[None,None,:]+norm[:,None,:]*epsilon[None,:,None]+epsilon[:,None]*epsilon[None,:]
            bound2[i]=np.maximum(bound2[i],e.max(axis=0));bound4[i]=np.maximum(bound4[i],(2*np.sqrt(A)*e+e*e).max(axis=0))
        print(dict(stage='independent_POST_input',completed=i+1),flush=True)
    C=covariance.reshape(2,1024,4,4);A=operator.reshape(2,1024,4,4,4)
    r['maximum_C_error']=float(abs(C-data['covariance']).max());r['maximum_A_error']=float(abs(A-data['operator']).max())
    assert r['maximum_C_error']<1e-16 and r['maximum_A_error']<1e-20
    for key,value in [('bound2',bound2),('bound4',bound4)]:
        assert np.max(abs(value/data[key]-1))<1e-10
    source=load(a.workspace/'baselines/idle_joint_cumulant_v1/evidence/observe1/report.json')
    sourceQ=[]
    for part in ['training','check']:
        path=a.workspace/'baselines/idle_excitation_moments_v1/evidence/observe1'/(part+'.npz')
        assert sha(path)==source['inputs'][str(path)]
        with np.load(path) as archive:z=archive['filtered'].astype(np.longdouble)
        z-=z.mean(axis=0);variance=np.mean(z*z,axis=0)
        sourceQ.append([(np.mean(z[:,b]**2*z[:,c]**2)-variance[b]*variance[c]-2*np.mean(z[:,b]*z[:,c])**2)/(variance[b]*variance[c]) for b,c in PAIRS])
    sourceQ=np.asarray(sourceQ,dtype=float);assert abs(sourceQ-data['sourceQ']).max()<1e-10
    states=[state(data['main'][b],C[b],A[b]) for b in range(2)]
    for b,s in enumerate(states):
        for key in s:
            scale=s['denominator'][:,None] if key=='terms' else s['denominator'] if key=='gaussian' else 1.
            error=float(abs((s[key]-observed['states'][b][key])/scale).max())
            assert error<1e-10,(b,key,error);r['maximum_normalized_budget_error']=max(r['maximum_normalized_budget_error'],error)
    kappa=solve(states[0],sourceQ[0]);r['kappa_relative_error']=float(abs(kappa/observed['allocation']['kappa']-1).max())
    assert r['kappa_relative_error']<1e-10
    assert observed['allocation']['generative']==bool(np.all(kappa>=0))
    leaves=[]
    for group in range(64):
        keep=np.arange(1024)//16!=group
        selected=[state(data['main'][b,keep],C[b,keep],A[b,keep]) for b in range(2)]
        coefficient=solve(selected[0],sourceQ[0]);leaves.append(np.r_[coefficient,predict(selected[0],coefficient),predict(selected[1],coefficient)])
    leaves=np.asarray(leaves)
    assert abs((leaves-data['leave'])/np.maximum(abs(data['leave']),1.)).max()<1e-10
    point=np.r_[kappa,predict(states[0],kappa),predict(states[1],kappa)]
    se=np.sqrt(63/64*np.sum((leaves-leaves.mean(axis=0))**2,axis=0));radius=special.stdtrit(63,.975)*se
    for key,value in [('point',point),('se',se),('low',point-radius),('high',point+radius),
                     ('estimated_plugin_bias',63*(leaves.mean(axis=0)-point))]:
        assert abs((value-observed['jackknife'][key])/np.maximum(abs(value),1.)).max()<1e-10,key
    for b,s in enumerate(states):
        assert abs(predict(s,kappa)-observed['new_predictions'][b]).max()<1e-10
        assert abs(predict(s,data['oldkappa'])-observed['old_predictions'][b]).max()<1e-10
    r.update(result='all2048_POST_kernels_source_budget_inverse_and64jackknife_verified',input_report_sha256=sha(a.input/'report.json'),
             conditional_time_MC_NOT_full_native_window=True,all_lag_curves_qualified=False,audio_or_runtime_changed=False)
except Exception as exc:
    r.update(result='failed',error=repr(exc));raise
finally:save(a.out/'report.json',r)
