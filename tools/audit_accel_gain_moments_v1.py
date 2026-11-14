"""Independent stationary-increment covariance contractions and geometric replay of all old gains."""
import argparse, math, os, shutil, sys
from pathlib import Path
parser=argparse.ArgumentParser(description=__doc__)
for key in ['workspace','input','out']:parser.add_argument('--'+key,type=Path,required=True)
args=parser.parse_args();sys.path.insert(0,str(args.workspace/'tools/python_deps'))
for key in ['OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','OMP_NUM_THREADS']:os.environ[key]='2'
import numpy as np
from research_archive_v1 import load,save,sha

args.out.mkdir(parents=True,exist_ok=False);shutil.copy2(__file__,args.out/'executed_auditor.py')
r=dict(result='running',input_sha256=sha(args.input/'report.json'),errors={},cases=0,runs=0,blocks=0)


def check(name,x,y,gate=1e-10,scale=None):
    x=np.asarray(x);y=np.asarray(y);error=float(abs(x-y).max())
    if scale is not None:error/=max(float(scale),1e-300)
    r['errors'][name]=max(error,r['errors'].get(name,0.))
    assert error<=gate,(name,error,gate)


def reference(G,tau,m,blocks,fs):
    coordinates=list(range(len(G)))*2;powers=[2]*len(G)+[4]*len(G)
    means=np.array([math.exp((p*p/2-p)*G[i,i]) for i,p in zip(coordinates,powers)])
    count=m*blocks;time=np.arange(count);rho=np.exp((-1/(fs*tau))*time)
    lag=np.zeros((blocks,len(means),len(means)))
    for a,(i,p) in enumerate(zip(coordinates,powers)):
        for b,(j,q) in enumerate(zip(coordinates,powers)):
            half=.5*p*q*G[i,j]*rho
            c=means[a]*means[b]*2*np.exp(half)*np.sinh(half)
            prefix=np.cumsum(c[1:]);weighted=np.cumsum(time[1:]*c[1:]);V=[0.]
            for block in range(1,blocks+1):
                n=block*m
                V.append(n*c[0]+(2*(n*prefix[n-2]-weighted[n-2]) if n>1 else 0.))
            lag[0,a,b]=V[1]/m**2
            for d in range(1,blocks):lag[d,a,b]=(V[d+1]-2*V[d]+V[d-1])/(2*m**2)
    full=np.empty((blocks*len(means),blocks*len(means)))
    for a in range(blocks):
        for b in range(blocks):full[a*len(means):(a+1)*len(means),b*len(means):(b+1)*len(means)]=lag[abs(b-a)]
    A=np.tile(np.eye(len(means))/blocks,(1,blocks));run=A@full@A.T
    return dict(mean=means,powers=np.array(powers),coordinate=np.array(coordinates),block_lag_covariance=lag,
        full_block_covariance=full,continuous_run_covariance=run,independent3_run_mean_covariance=run/3)


def gains(L,tau,frames,seed):
    rng=np.random.default_rng(seed);state=L@rng.standard_normal(len(L));white=rng.standard_normal((frames,len(L)))
    rate=1/(48000*tau);innovations=(white@L.T)*math.sqrt(-math.expm1(-2*rate));out=np.empty_like(white)
    for start in range(0,frames,512):
        length=min(512,frames-start);power=np.exp(-rate*np.arange(1,length+1))
        latent=power[:,None]*(state[None,:]+np.cumsum(innovations[start:start+length]/power[:,None],axis=0))
        out[start:start+length]=np.exp(latent-np.diag(L@L.T)[None,:]);state=latent[-1]
    return out


try:
    run=load(args.input/'report.json');assert run['result']=='all12_native_gain_power_moments_and_existing_paths_complete'
    for name,digest in run['sources'].items():assert sha(args.input/'exact_sources'/name)==digest
    assert sha(args.input/'known.npz')==run['known_sha256']
    with np.load(args.input/'known.npz') as known:
        ref=reference(known['gamma'],.2,5,3,100)
        for key in ref:check('known_'+key,ref[key],known[key],1e-12)
        check('known_independent_quadrature_matrix',ref['full_block_covariance'],known['full_quadrature_covariance'],1e-12)
    parent=args.workspace/'baselines/accel_upper_realization_v1'
    assert sha(parent/'manifest.json')==run['parent_manifest_sha256'];table={v['path']:v['sha256'] for v in load(parent/'manifest.json')['files']}
    for name,digest in run['parent_files'].items():assert sha(parent/name)==digest==table[name]
    for row in run['observations']:
        assert sha(args.input/row['file'])==row['sha256']
        with np.load(args.input/row['file']) as f,np.load(parent/row['model_parent_file']) as model:
            L=model['L'];G=L@L.T;tau=float(model['parameters'][-1]);m=len(model['tile'])*480
            check('gamma',f['gamma'],G,0);check('tau',f['tau'],tau,0);check('frames_per_block',f['frames_per_block'],m,0)
            ref=reference(G,tau,m,8,48000)
            for key in ref:
                scale=max(abs(ref[key]).max(),abs(f[key]).max()) if 'covariance' in key else None
                check('all_'+key,ref[key],f[key],1e-10,scale)
            full=ref['full_block_covariance'];scale=abs(full).max()
            check('full_covariance_symmetry',full,full.T,1e-12,scale)
            minimum=float(np.linalg.eigvalsh(full).min());assert minimum>=-1e-10*max(scale,1e-300)
            actual=[]
            for record in row['records']:
                warm=record['warmup_frames'];g=gains(L,tau,record['frames']+warm,record['gain_seed'])[warm:]
                values=np.column_stack([g[:,i]**p for p in [2,4] for i in range(4)])
                block=np.array([[math.fsum(values[b*m:(b+1)*m,i])/m for i in range(8)] for b in range(8)])
                actual.append(block);check('original_squared_gain_mean',block.mean(axis=0)[:4],record['gain_squared_mean'],1e-10)
                r['runs']+=1;r['blocks']+=8
            actual=np.array(actual);actual_run=actual.mean(axis=1);mean=actual_run.mean(axis=0)
            check('all_actual_blocks',actual,f['actual_block'],1e-10);check('all_actual_runs',actual_run,f['actual_run'],1e-10)
            check('all_actual_means',mean,f['actual_mean'],1e-10);sd=np.sqrt(np.diag(ref['independent3_run_mean_covariance']))
            check('all_pooled3_sd',sd,f['pooled3_sd'],1e-10);defined=sd>0;score=np.zeros(8)
            score[defined]=(mean-ref['mean'])[defined]/sd[defined]
            check('all_defined',defined.astype(int),f['standardized_defined'].astype(int),0)
            check('all_descriptive_standardized_differences',score,f['descriptive_standardized_difference'],1e-9)
            for key,array in [('expected',ref['mean']),('actual_mean',mean),('pooled3_sd',sd),('descriptive_standardized_difference',score)]:
                check('reported_'+key,row[key],array,1e-9 if 'standardized' in key else 1e-10)
        r['cases']+=1;save(args.out/'report.json',r);print(dict(cases=r['cases'],segment=row['segment'],branch=row['branch']),flush=True)
    assert r['cases']==12 and r['runs']==36 and r['blocks']==288
    r.update(result='passed',all_native_covariance_operators=True,all_full64x64_block_covariances=True,
             all_existing_paths_and_moments=True,all_signed_crosscovariances_preserved=True,
             not_VarS_or_conditional_quadratic_uncertainty=True,new_audio=False)
except Exception as exc:r.update(result='failed',error=repr(exc));raise
finally:save(args.out/'report.json',r)
print(r,flush=True)
