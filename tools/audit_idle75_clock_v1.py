"""Independent audit of a FAILED known inverse, without rescuing its parameters."""
import argparse,os,shutil,sys
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__)
for key in ['workspace','input','out']:p.add_argument('--'+key,type=Path,required=True)
a=p.parse_args();repo=Path(__file__).resolve().parents[1];sys.path.insert(0,str(a.workspace/'tools/python_deps'))
for key in ['OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','OMP_NUM_THREADS']:os.environ[key]='2'
import numpy as np
from scipy import linalg
from research_archive_v1 import load,save,sha

a.out.mkdir(parents=True,exist_ok=False);shutil.copy2(__file__,a.out/'executed_auditor.py')
source=load(a.input/'report.json');assert source['result']=='failed' and not source['models']
assert source['known']['inverse']['available'] and source['known']['parameter_error']>1e-5
plan=repo/'research/idle75_clock_v1_inverse_diagnosis.json';shutil.copy2(plan,a.out/plan.name)
r=dict(result='running',input_sha256=sha(a.input/'report.json'),plan_sha256=sha(plan),errors={},QR_factorizations=0,profile=[])
model=load(a.input/'row.json');h=np.array(model['taps']);C=np.array(model['covariance']);V=model['variance'];rate=model['node_rate']
starts=np.arange(12000,122401,960);window=np.hanning(9601)[:-1];sqrtw=np.sqrt(window)
profile=load(a.workspace/'baselines/fixed_source_profiles_v1/evidence/trial1/F2_tailpipe/profile.json')
freq=np.array(profile['modal']['frequencies_hz'])
amp=load(a.workspace/'baselines/idle_local_partition_v1/evidence/compile2/model.json')['main_amplitude_LR'][0][0]
caches=[];streams=[]


def error(key,x,y,tolerance):
    d=float(np.max(np.abs(np.asarray(x)-np.asarray(y))))
    r['errors'][key]=max(r['errors'].get(key,0.),d);assert d<=tolerance,(key,d,tolerance)


def native(values,parameters):
    speed,strength=parameters;q=np.arange(144000)/48000*rate;position=q*speed;k=np.floor(position).astype(int);u=position-k
    # Independent Catmull-Rom polynomial in four actual node values.
    a0,b,c,d=[values[k+j] for j in [1,2,3,4]]
    raw=(2*b+(-a0+c)*u+(2*a0-5*b+4*c-d)*u*u+(-a0+3*b-3*c+d)*u**3)/2
    raw_derivative=((-a0+c)+2*(2*a0-5*b+4*c-d)*u+3*(-a0+3*b-3*c+d)*u*u)/2
    w=np.stack((u*(-1+2*u-u*u)/2,1+u*u*(-5+3*u)/2,u*(1+4*u-3*u*u)/2,u*u*(-1+u)/2),axis=1)
    dw=np.stack(((-1+4*u-3*u*u)/2,u*(-10+9*u)/2,(1+8*u-9*u*u)/2,u*(-2+3*u)/2),axis=1)
    variance=sum(w[:,i]*w[:,j]*C[i,j] for i in range(4) for j in range(4))
    derivative=sum((dw[:,i]*w[:,j]+w[:,i]*dw[:,j])*C[i,j] for i in range(4) for j in range(4))
    scale=np.sqrt(V/variance);x=raw*scale;dx=(raw_derivative-raw*derivative/(2*variance))*scale*q
    g=np.exp(strength*x-strength**2*V)
    jac=np.stack((g*strength*dx,g*(x-2*strength*V)),axis=1)
    return g,jac,x


def covariance(coefficient,dc=None):
    u=coefficient.real/amp;u-=u.mean()
    if dc is not None:d=dc.real/amp;d-=d.mean(axis=0)
    values=[];derivatives=[]
    for lag in [0,2,5,10]:
        lo=u[:len(u)-lag or None];hi=u[lag:];values.append(sum(lo*hi)/len(lo))
        if dc is not None:
            derivatives.append(np.sum(d[:len(u)-lag or None]*hi[:,None]+lo[:,None]*d[lag:],axis=0)/len(lo))
    return np.array(values),np.array(derivatives)


def evaluate(parameters):
    values=[];derivatives=[]
    for stream,cache in zip(streams,caches):
        g,jac,_=native(stream,parameters);wg=np.stack([g[first:first+9600] for first in starts])
        dj=np.stack([jac[first:first+9600] for first in starts])
        coefficient=cache['constant']+np.sum(cache['h']*wg,axis=1)
        dc=np.sum(cache['h'][:,:,None]*dj,axis=1)
        value,derivative=covariance(coefficient,dc);values.append(value);derivatives.append(derivative)
    return np.mean(values,axis=0),np.mean(derivatives,axis=0)


try:
    for path,digest in source['sources'].items():assert sha(repo/path)==digest==sha(a.input/'exact_sources'/path)
    for path,digest in source['inputs'].items():assert sha(path)==digest
    for i in range(4):
        for j in range(4):error('FIR_all_crossnode_covariance',sum(np.dot(h[t],h[t+abs(i-j)]) for t in range(len(h)-abs(i-j))),C[i,j],1e-14)
    for row in source['streams']:
        file=a.input/row['file'];assert sha(file)==row['sha256']
        with np.load(file) as n:f={k:n[k] for k in n.files}
        seed=row['seed'];white=np.random.Generator(np.random.PCG64(seed^0x619A2EF5B37C)).standard_normal(f['white'].shape)
        error('all_white',white,f['white'],0)
        nodes=sum(np.convolve(white[:,j],h[:,j])[len(h)-1:len(h)-1+len(f['nodes'])] for j in range(3))
        error('all_FIR_nodes',nodes,f['nodes'],1e-12);streams.append(nodes)
        trace=a.workspace/f'baselines/idle_phase_amplitude_v1/evidence/render2/trace_{seed}.npz'
        with np.load(trace) as n:oldx=n['native_log'][:144000,0]
        oldmodel=load(a.workspace/'baselines/idle_phase_amplitude_v1/evidence/render2/model.json')
        oldg=np.exp(oldx-np.array(oldmodel['training_covariance'])[0,0]);error('old_gain_binding',oldg,f['old_gain'],1e-12)
        z=f['phasors'];carrier=np.exp(2j*np.pi*np.arange(144000)[:,None]/48000*freq);carrier[:,[1,2,4]]=z
        A=np.column_stack((carrier.real,carrier.imag,np.ones(len(z))));response=[];constant=[]
        for first in starts:
            Q,R=np.linalg.qr(A[first:first+9600]*sqrtw[:,None],mode='reduced')
            P=linalg.solve_triangular(R,Q.T*sqrtw);p75=P[1]-1j*P[14]
            h75=p75*z[first:first+9600,0].real*amp
            response.append(h75);constant.append(p75@f['baseline_mix'][first:first+9600]-h75@oldg[first:first+9600]);r['QR_factorizations']+=1
        cache=dict(h=np.array(response),constant=np.array(constant));caches.append(cache)
        error('all_QR_response_h',cache['h'],f['response_h'],1e-12);error('all_QR_constant',cache['constant'],f['response_constant'],1e-12)
    known=source['known']['inverse'];target=np.array(known['TRAIN_target']);variance=target[0]
    for row in known['trace']:
        value,jac=evaluate(row['parameters']);error('all_trace_moments',value,row['moments'],1e-12)
        cost=float(np.sum(((value-target)/variance)**2));error('all_trace_costs',cost,row['squared_error'],1e-10)
    final,jac=evaluate(known['parameters']);singular=np.linalg.svd(jac/variance,compute_uv=False)
    error('Jacobian_singular_values',singular,known['singular_values'],1e-10)
    error('Jacobian_condition',singular[0]/singular[-1],known['condition'],1e-9)
    truth=np.array(source['known']['truth']);true,jactrue=evaluate(truth)
    error('known_truth_zero_moments',true,target,1e-12)
    r['known_returned_parameters']=known['parameters'];r['known_truth']=truth.tolist()
    r['known_parameter_error']=float(abs(np.array(known['parameters'])-truth).max())
    r['returned_scaled_cost']=float(np.sum(((final-target)/variance)**2));r['truth_scaled_cost']=float(np.sum(((true-target)/variance)**2))
    r['returned_scaled_gradient']=(2*(jac/variance).T@((final-target)/variance)).tolist()
    for fraction in np.linspace(0,1,21):
        p0=np.array(known['parameters'])*(1-fraction)+truth*fraction;value,_=evaluate(p0)
        r['profile'].append(dict(fraction=float(fraction),parameters=p0.tolist(),moments=value.tolist(),scaled_cost=float(np.sum(((value-target)/variance)**2))))
    failed=load(a.input.parent/'fit1/report.json');diag=load(a.input.parent/'derivative_diagnosis1/report.json')
    assert failed['result']=='failed' and diag['result']=='cubic_node_seam_truncation_identified'
    assert diag['original_report_sha256']==sha(a.input.parent/'fit1/report.json')
    with np.load(a.input.parent/'derivative_diagnosis1/derivatives.npz') as n:
        g,jac,x=native(n['nodes'],[1.,1.]);error('diagnosed_native_gain',g,n['gain'],1e-12)
        error('diagnosed_native_analytic_jacobian',jac,n['analytic_jacobian'],1e-10)
        assert abs(n['branch_preserving_0']-jac[:,0]).max()<1e-6
    assert r['QR_factorizations']==348 and r['known_parameter_error']>1e-5 and r['returned_scaled_cost']>1e-8
    r.update(result='failed_known_inverse_independently_confirmed',new_source_fit=False,new_audio=False,
        analytic_derivative_and_forward_response_consistent=True,known_truth_initialization_or_new_optimizer=False,
        next='Expected ensemble moments through original observer, not parameter-fitting a short random take. Stochastic takes for validation; no original gate/bounds/seed/iteration change.')
except Exception as exc:r.update(result='audit_failed',error=repr(exc));raise
finally:save(a.out/'report.json',r)
print(dict(result=r['result'],parameter_error=r.get('known_parameter_error'),returned_cost=r.get('returned_scaled_cost'),truth_cost=r.get('truth_scaled_cost'),errors=r['errors']))
