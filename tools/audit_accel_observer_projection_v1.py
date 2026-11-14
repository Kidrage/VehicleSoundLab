"""Independent full convolution, continuous AR1 contractions and integral exponential remainder."""
import argparse,math,os,shutil,sys
from pathlib import Path
parser=argparse.ArgumentParser(description=__doc__)
for key in ['workspace','input','out']:parser.add_argument('--'+key,type=Path,required=True)
args=parser.parse_args();sys.path.insert(0,str(args.workspace/'tools/python_deps'))
for key in ['OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','OMP_NUM_THREADS']:os.environ[key]='2'
import numpy as np
from scipy.signal import fftconvolve,lfilter
from numpy.polynomial.legendre import leggauss
from research_archive_v1 import load,save,sha

args.out.mkdir(parents=True,exist_ok=False);shutil.copy2(__file__,args.out/'executed_auditor.py')
r=dict(result='running',input_sha256=sha(args.input/'report.json'),errors={},cases=0,coordinates=0)


def check(name,x,y,gate=1e-10,relative=False):
    x=np.asarray(x);y=np.asarray(y);error=float(abs(x-y).max())
    if relative:
        scale=float(max(abs(x).max(),abs(y).max()))
        if scale:error/=scale
    r['errors'][name]=max(error,r['errors'].get(name,0.));assert error<=gate,(name,error,gate)


def convolution_rows(kernel,n):
    return fftconvolve(np.r_[kernel[1:n][::-1],kernel[:n]],np.ones(n),mode='full')[n-1:2*n-1]


def reference(gamma,tau,R,tile,size,blocks,runs,fs):
    counts=[(tag,np.flatnonzero(tile==tag)) for tag in np.unique(tile)];length=max(len(ii) for _,ii in counts)*size
    rho=np.exp(-np.arange(length)/(fs*tau));rc=np.array([R[i]/R[0] if i<len(R) else 0. for i in range(length)])
    h=(1+2*rc*rc)*np.exp(4*gamma*rho);window=convolution_rows(h,size);t=np.zeros(len(tile)*size);a=np.zeros_like(t)
    for tag,ii in counts:
        m=len(ii)
        if m==1:continue
        group=convolution_rows(h,m*size);where=slice(ii[0]*size,(ii[-1]+1)*size)
        t[where]=(np.tile(window,m)-group/m)/(len(tile)*size**2)
        a[where]=((1-2/m)*np.tile(window,m)+group/m)/(len(tile)*size**2)
    coefficient=math.exp(-1/(fs*tau))
    def contract(v):
        value=np.tile(v,blocks)/blocks;filtered=lfilter([1.],[1.,-coefficient],value)
        return math.fsum(value*value)+2*coefficient*math.fsum(value[1:]*filtered[:-1])
    qs=contract(t);qa=contract(a);x=16*gamma;z,w=leggauss(32);nodes=(z+1)/2
    rem=x*x*math.fsum(w/2*(1-nodes)*np.exp(x*nodes));first=16*gamma*qs;remainder=rem*qa
    return dict(expected=math.fsum(t),signed_ou_quadratic_run=qs,absolute_ou_quadratic_run=qa,exponential_remainder=rem,
        first_variance_run=first,remainder_variance_upper_run=remainder,variance_upper_run=first+remainder,
        first_variance_pooled=first/runs,remainder_variance_upper_pooled=remainder/runs,variance_upper_pooled=(first+remainder)/runs),t,a


try:
    run=load(args.input/'report.json');assert run['result']=='all12_signed_native_observer_projections_and_remainders_complete'
    for name,digest in run['sources'].items():assert sha(args.input/'exact_sources'/name)==digest
    assert sha(args.input/'known.npz')==run['known_sha256']
    with np.load(args.input/'known.npz') as known:
        for i,item in enumerate(run['known']['fixtures']):
            ref,t,a=reference(item['gamma'],item['tau'],known[f'R{i}'],np.array(item['tile']),item['size'],item['blocks'],1,100)
            check('known_signed_rows',t,known[f't{i}'],1e-12);check('known_absolute_rows',a,known[f'a{i}'],1e-12)
            for key,value in ref.items():check('known_'+key,value,item[key],1e-11)
            assert ref['first_variance_run']<=item['exact_path_variance']+1e-11<=ref['variance_upper_run']+2e-11
    parent=args.workspace/'baselines/accel_observer_bound_v1';assert sha(parent/'manifest.json')==run['parent_manifest_sha256']
    table={v['path']:v['sha256'] for v in load(parent/'manifest.json')['files']}
    for name,digest in run['parent_files'].items():assert sha(parent/name)==digest==table[name]
    for row in run['observations']:
        assert sha(args.input/row['file'])==row['sha256']
        with np.load(args.input/row['file']) as f,np.load(parent/row['old_parent_file']) as old:
            for key in ['actual','conditional','source_target','gamma','tau','tile','carrier_R','path_difference','carrier_difference','total_difference']:
                check('old_'+key,f[key],old[key],0)
            check('prior_path_upper',f['prior_path_upper'],old['path_variance_bound_pooled'],0)
            check('prior_carrier_upper',f['prior_carrier_upper'],old['carrier_variance_bound_pooled'],0)
            check('prior_total_upper',f['prior_total_upper'],old['total_variance_bound_pooled'],0)
            for i in range(4):
                ref,t,a=reference(float(old['gamma'][i]),float(old['tau']),old['carrier_R'][:,i],old['tile'],480,8,3,48000)
                check('all_signed_coefficients',t,f['signed_coefficient'][:,i],1e-10,True);check('all_absolute_coefficients',a,f['absolute_coefficient'][:,i],1e-10,True)
                for key,value in ref.items():check('all_'+key,value,f[key][i],1e-10,True)
                check('frozen_expected',ref['expected'],old['expected'][i],1e-10)
                r['coordinates']+=1
            combined=np.minimum(f['variance_upper_pooled'],old['path_variance_bound_pooled'])
            check('combined_path',combined,f['combined_path_upper'],0);check('combined_total',combined+old['carrier_variance_bound_pooled'],f['combined_total_upper'],0)
            assert np.all(f['first_variance_pooled']<=combined+1e-12)
            for name in ['path','total']:
                delta=f[name+'_difference'];b=f['combined_'+name+'_upper'];prob=np.array([1. if d==0 else min(1.,v/(d*d)) for v,d in zip(b,delta)])
                check(name+'_tail',prob,f[name+'_marginal_tail_upper'],1e-12)
            for reported,key in [('first_variance_pooled','first_variance_pooled'),('projection_upper_pooled','variance_upper_pooled'),('combined_path_upper','combined_path_upper'),
                ('combined_total_upper','combined_total_upper'),('path_tail_upper','path_marginal_tail_upper'),('total_tail_upper','total_marginal_tail_upper')]:check('reported_'+reported,row[reported],f[key],1e-12)
        r['cases']+=1;save(args.out/'report.json',r);print(dict(cases=r['cases'],segment=row['segment'],branch=row['branch']),flush=True)
    assert r['cases']==12 and r['coordinates']==48
    r.update(result='passed',all_signed_native_coefficients=True,all_whole_continuous_OU_quadratics=True,
        all_integral_remainders_bounds_and_old_values=True,first_projection_not_complete_variance=True,new_audio=False)
except Exception as exc:r.update(result='failed',error=repr(exc));raise
finally:save(args.out/'report.json',r)
print(r,flush=True)
