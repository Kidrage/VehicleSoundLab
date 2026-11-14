"""Independent full-convolution row operators and every native observer-bound result."""
import argparse,math,os,shutil,sys
from pathlib import Path
parser=argparse.ArgumentParser(description=__doc__)
for key in ['workspace','input','out']:parser.add_argument('--'+key,type=Path,required=True)
args=parser.parse_args();sys.path.insert(0,str(args.workspace/'tools/python_deps'))
for key in ['OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','OMP_NUM_THREADS']:os.environ[key]='2'
import numpy as np
from scipy.signal import fftconvolve
from research_archive_v1 import load,save,sha

args.out.mkdir(parents=True,exist_ok=False);shutil.copy2(__file__,args.out/'executed_auditor.py')
r=dict(result='running',input_sha256=sha(args.input/'report.json'),errors={},cases=0,coordinates=0)


def check(name,x,y,gate=1e-10,relative=False):
    x=np.asarray(x);y=np.asarray(y);error=float(abs(x-y).max())
    if relative:
        scale=float(max(abs(x).max(),abs(y).max()))
        if scale:error/=scale
    r['errors'][name]=max(error,r['errors'].get(name,0.));assert error<=gate,(name,error,gate)


def window_rows(kernel,n):
    even=np.r_[kernel[1:n][::-1],kernel[:n]]
    return fftconvolve(even,np.ones(n),mode='full')[n-1:2*n-1]


def reference(gamma,tau,R,tile,size,blocks,runs,fs):
    tags,counts=np.unique(tile,return_counts=True);extent=max(counts)*size
    time=np.arange(extent);corr=np.array([R[t]/R[0] if t<len(R) else 0. for t in time]);rho=np.exp(-time/(fs*tau))
    E=np.exp(8*gamma+16*gamma*rho);H=1+2*corr*corr
    kernels=dict(H=H,J=H*E,C=E*(3+12*corr*corr),D=np.exp(4*gamma*rho)*H-1)
    W={key:window_rows(kernel,size) for key,kernel in kernels.items()};N=len(tile);Gu=[];Gc=[];means=[]
    for m in counts:
        if m==1:continue
        Babs=2*(1-1/m)/(N*size);groups={key:window_rows(kernel,m*size) for key,kernel in kernels.items()}
        ah=((1-2/m)*np.tile(W['H'],m)+groups['H']/m)/(N*size**2)
        jh=((1-2/m)*np.tile(W['J'],m)+groups['J']/m)/(N*size**2)
        jc=((1-2/m)*np.tile(W['C'],m)+groups['C']/m)/(N*size**2)
        Gu.append(16*math.fsum(ah*jh));Gc.append(16*Babs*math.fsum(jc))
        means.append((m*math.fsum(W['D'])-math.fsum(groups['D'])/m)/(N*size**2))
    Gu=math.fsum(Gu);Gc=math.fsum(Gc);frames=N*size*blocks
    a=(frames-1)//2;b=frames-1-a
    Lu=gamma*(1+math.fsum(np.exp(-np.arange(1,a+1)/(fs*tau)))+math.fsum(np.exp(-np.arange(1,b+1)/(fs*tau))))
    if frames>=2*len(R)-1:Lc=1+2*math.fsum(abs(R[1:]/R[0]))
    else:
        delta=abs(np.arange(frames)[:,None]-np.arange(frames)[None,:]);C=np.zeros_like(delta,dtype=float);valid=delta<len(R);C[valid]=R[delta[valid]]/R[0]
        Lc=max(math.fsum(abs(row)) for row in C)
    path=Lu*Gu/blocks;carrier=Lc*Gc/blocks
    return dict(expected=math.fsum(means),conditional_gradient_bound_oneblock=Gu,carrier_normalized_gradient_bound_oneblock=Gc,
        latent_covariance_norm_bound=Lu,normalized_carrier_covariance_norm_bound=Lc,path_variance_bound_run=path,
        carrier_variance_bound_run=carrier,total_variance_bound_run=path+carrier,path_variance_bound_pooled=path/runs,
        carrier_variance_bound_pooled=carrier/runs,total_variance_bound_pooled=(path+carrier)/runs)


try:
    run=load(args.input/'report.json');assert run['result']=='all12_actual_energy_observer_variance_upper_bounds_complete'
    for name,digest in run['sources'].items():assert sha(args.input/'exact_sources'/name)==digest
    assert sha(args.input/'known.npz')==run['known_sha256']
    with np.load(args.input/'known.npz') as known:
        for i,item in enumerate(run['known']['fixtures']):
            ref=reference(item['gamma'],item['tau'],known[f'R{i}'],np.array(item['tile']),item['size'],item['blocks'],1,100)
            for key,value in ref.items():check('known_'+key,value,item[key],1e-11)
            check('known_exact_mean',ref['expected'],item['oracle']['expected'],1e-11)
            for key in ['path','carrier','total']:assert item['oracle'][key+'_variance']<=ref[key+'_variance_bound_run']+1e-11
    parent=args.workspace/'baselines/accel_upper_conditional_v1';assert sha(parent/'manifest.json')==run['parent_manifest_sha256']
    table={v['path']:v['sha256'] for v in load(parent/'manifest.json')['files']}
    for name,digest in run['parent_files'].items():assert sha(parent/name)==digest==table[name]
    for row in run['observations']:
        assert sha(args.input/row['file'])==row['sha256']
        with np.load(args.input/row['file']) as f,np.load(parent/row['model_parent_file']) as model,np.load(parent/row['carrier_parent_file']) as c,np.load(parent/row['old_parent_file']) as old:
            G=model['L']@model['L'].T;tau=float(model['parameters'][-1]);R=c['covariance'][len(c['impulse'])-1:][:,[0,1,2,3],[0,1,2,3]]
            check('gamma',f['gamma'],np.diag(G),0);check('carrier_R',f['carrier_R'],R,0);check('tile',f['tile'],model['tile'],0);check('tau',f['tau'],tau,0)
            for key in ['actual','conditional','source_target']:check('old_'+key,f[key],old[key],0)
            for i in range(4):
                ref=reference(G[i,i],tau,R[:,i],model['tile'],480,8,3,48000)
                for key,value in ref.items():
                    check('all_'+key,value,f[key][i],1e-10,True);check('reported_'+key,row['bounds'][i][key],f[key][i],1e-12)
                check('frozen_expected',ref['expected'],model['prediction'][5,i,i],1e-10)
                r['coordinates']+=1
            deltas={'path':(old['conditional']-old['expected']).mean(axis=(0,1)),
                'carrier':(old['actual']-old['conditional']).mean(axis=(0,1)),'total':(old['actual']-old['expected']).mean(axis=(0,1))}
            for name,delta in deltas.items():
                check(name+'_difference',delta,f[name+'_difference'],1e-12)
                bound=f[name+'_variance_bound_pooled'];prob=np.array([1. if v==0 else min(1.,b/(v*v)) for b,v in zip(bound,delta)])
                check(name+'_Chebyshev',prob,f[name+'_marginal_Chebyshev_upper'],1e-12)
            check('reported_total_tail',row['marginal_total_tail_upper'],f['total_marginal_Chebyshev_upper'],0)
        r['cases']+=1;save(args.out/'report.json',r);print(dict(cases=r['cases'],segment=row['segment'],branch=row['branch']),flush=True)
    assert r['cases']==12 and r['coordinates']==48
    r.update(result='passed',all_native_gradient_and_operator_bounds=True,all_old24block_values_unchanged=True,
        all_expected_means_and_fixed_coordinate_tail_arithmetic=True,upper_bounds_not_exact_variances=True,new_audio=False)
except Exception as exc:r.update(result='failed',error=repr(exc));raise
finally:save(args.out/'report.json',r)
print(r,flush=True)
