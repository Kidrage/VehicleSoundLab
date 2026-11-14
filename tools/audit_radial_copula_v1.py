"""Independent quantile quadrature, ranks/AR, joint moments and direct OSC samples."""
import argparse
import ast
import math
import os
from pathlib import Path
import shutil
import sys
from research_archive_v1 import load,save,sha


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for n in ('workspace','study','out'):p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args();repo=Path(__file__).resolve().parents[1]
    for n in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):os.environ[n]='2'
    sys.path.insert(0,str(a.workspace/'tools/python_deps'))
    import numpy as np
    import soundfile as sf
    from scipy import signal,special
    a.out.mkdir(parents=True,exist_ok=False);shutil.copy2(__file__,a.out/'executed_audit.py')
    report=dict(result='running',cases=[],QMC_cases=0,new_waveforms=0,max_quadrature_mean_power_relative_error=0.,
                max_normalized_joint_moment_error=0.,max_direct_wave_error_FS=0.,max_AR_error=0.)
    try:
        producer=load(a.study/'report.json')
        assert producer['result'] in ('known_radial_phase_separation_passed','six_radial_copula_models_and_two_anchor_audio_ready')
        for n,h in producer['sources'].items():
            snapshot=a.study/'exact_sources'/n
            assert sha(snapshot)==h
            if sha(repo/n)!=h:
                assert producer['stage']=='known' and n=='tools/run_radial_copula_v1.py'
                old,current=[ast.parse(p.read_text(encoding='utf-8')) for p in (snapshot,repo/n)]
                def branch(tree):
                    nodes=[v for v in ast.walk(tree) if isinstance(v,ast.If) and ast.unparse(v.test)=="a.stage == 'known'"]
                    assert len(nodes)==1
                    helpers=[v for v in ast.walk(tree) if isinstance(v,ast.FunctionDef) and v.name in ('fit','consume','command')]
                    return [ast.dump(v,include_attributes=False) for v in nodes[0].body+helpers]
                assert branch(old)==branch(current)
                report['unchanged_known_branch_and_helpers_AST_exact']=True
        for n,h in producer['inputs'].items():assert sha(n)==h
        plan=load(a.study/'exact_sources/research/radial_copula_v1_plan.json');g=plan['gates']
        bands=[[3000,6000],[6000,8000],[8000,10000],[10000,14000]]
        def inverse(table,normal):
            probability=(1+special.erf(normal/math.sqrt(2)))/2
            n=len(table);positions=np.r_[0,(np.arange(n)+.5)/n,1]
            return np.column_stack([np.interp(probability[:,j],positions,np.r_[table[0,j],table[:,j],table[-1,j]]) for j in range(table.shape[1])])
        def arrays(profile,normal,variable):
            size=profile['amplitude'].shape[1]
            amp=inverse(profile['amplitude'],normal[:,:size]).reshape(len(normal),-1,2)
            phase=inverse(profile['phase'],normal[:,size:]).reshape(len(normal),-1,2) if variable else np.broadcast_to(profile['fixed_phase'],amp.shape)
            return amp,phase
        def measure(amp,phase,root):
            q=[];coherence=[];hz=np.arange(1,amp.shape[1]+1)*root
            z=amp*np.exp(1j*phase)
            for lo,hi in bands:
                mask=(hz>=lo)&(hz<hi)
                for c in (0,1):q.append((amp[:,mask,c]**2).sum(axis=1)/2)
                cross=(z[:,mask,0]*z[:,mask,1].conj()).sum(axis=1).mean()
                energy=(amp[:,mask,:]**2).sum(axis=1).mean(axis=0)
                coherence.append(cross/np.sqrt(energy.prod()) if energy.prod()>0 else 0j)
            q=np.array(q).T;mean=q.mean(axis=0)
            cov=np.cov(q,rowvar=False,ddof=0)
            return q,mean,cov,np.array(coherence)
        def check_moments(saved,amp,phase,root,prefix):
            q,mean,cov,coherence=measure(amp,phase,root)
            assert abs(saved[prefix+'power']-q).max()<=2e-12*mean.max()
            normalized=abs(saved[prefix+'covariance']-cov)/np.outer(mean,mean)
            error=float(normalized.max());assert error<2e-9
            report['max_normalized_joint_moment_error']=max(report['max_normalized_joint_moment_error'],error)
            assert abs(saved[prefix+'mean']/mean-1).max()<2e-12
            assert abs(saved[prefix+'complex_coherence']-coherence).max()<2e-12
        def state(profile,count,seed):
            rho=np.r_[profile['rho'],profile['residual_rho']]
            noise=np.random.Generator(np.random.PCG64(seed)).standard_normal((count,len(rho)))
            result=np.empty_like(noise)
            for j,r in enumerate(rho):
                scale=math.sqrt(1-r*r)
                result[:,j]=signal.lfilter([scale],[1.,-r],noise[:,j],zi=[(1-scale)*noise[0,j]])[0]
            assert abs(result[0]-noise[0]).max()<1e-14
            expected=rho*result[:-1]+np.sqrt(1-rho*rho)*noise[1:]
            error=float(abs(result[1:]-expected).max());assert error<2e-13
            report['max_AR_error']=max(report['max_AR_error'],error)
            return result
        def sparse_wave(profile,path,root,seconds,seed,variable):
            wave,rate=sf.read(path,always_2d=True)
            assert rate==48000 and len(wave)==round(seconds*48000) and np.isfinite(wave).all()
            indices=sorted(set(np.linspace(0,len(wave)-1,64).astype(int).tolist()+[0,1,36,37,187,188,1023,1024,1025]))
            indices=np.array(indices,dtype=int)
            rho=np.r_[profile['rho'],profile['residual_rho']];k=len(profile['rho'])
            endpoint=state(profile,int(np.floor((len(wave)-1)*root/12000))+2,seed)
            positions=indices*root/12000;at=np.floor(positions).astype(int);u=positions-at
            left,right=endpoint[at],endpoint[at+1]
            raw=((1-u[:,None])*left+u[:,None]*right)/np.sqrt((1-u[:,None])**2+u[:,None]**2+2*rho*u[:,None]*(1-u[:,None]))
            normal=np.einsum('nk,dk->nd',raw[:,:k],profile['basis'],optimize=False)+raw[:,k:]*profile['residual_std']
            amplitude,phase=arrays(profile,normal,variable)
            want=[]
            for n,A,P in zip(indices,amplitude,phase):
                base=math.fmod(2*math.pi*float(n)*root/48000,2*math.pi)
                out=[]
                for c in (0,1):
                    terms=[]
                    for h in range(1,len(A)+1):
                        x=max(0.,min(1.,(h*root-19200)/2400))
                        terms.append(A[h-1,c]*(1-3*x*x+2*x*x*x)*math.cos(h*base+P[h-1,c]))
                    out.append(math.fsum(terms))
                want.append(out)
            want=np.array(want);error=abs(wave[indices]-want)
            bound=.5001*np.spacing(abs(want.astype('float32'))).astype(float)+g['independent_wave_absolute_FS']
            assert np.all(error<=bound),float((error-bound).max())
            report['max_direct_wave_error_FS']=max(report['max_direct_wave_error_FS'],float(error.max()))
            report['new_waveforms']+=1
        for row in producer['cases']:
            folder=a.study/row['label']
            assert sha(folder/'profile.npz')==row['profile_sha256'] and sha(folder/'training.npz')==row['training_sha256']
            profile=dict(np.load(folder/'profile.npz'));training=np.load(folder/'training.npz')
            n=len(profile['amplitude']);nodes,weights=np.polynomial.legendre.leggauss(3)
            knots=np.r_[0,(np.arange(n)+.5)/n,1]
            second=np.zeros(profile['amplitude'].shape[1]);fourth=np.zeros_like(second)
            for i,(lo,hi) in enumerate(zip(knots[:-1],knots[1:])):
                a0=profile['amplitude'][max(0,i-1)];b=profile['amplitude'][min(n-1,i)]
                for x,w in zip(nodes,weights):
                    val=a0*(1-(x+1)/2)+b*(x+1)/2
                    second+=w*(hi-lo)*val**2/2;fourth+=w*(hi-lo)*val**4/2
            target=profile['target_amplitude_second']
            rel=np.divide(abs(second-target),target,out=np.zeros_like(target),where=target>0)
            assert rel.max()<=g['mean_power_relative'] and (second[target==0]==0).all()
            report['max_quadrature_mean_power_relative_error']=max(report['max_quadrature_mean_power_relative_error'],float(rel.max()))
            source=training['source_rows'].reshape(n,-1,2,2);z=source[...,0]+1j*source[...,1]
            amplitude=abs(z).reshape(n,-1)
            assert abs(amplitude-training['amplitude']).max()<1e-15
            phase=training['phase_unwrapped']
            assert abs(np.exp(1j*phase)-np.exp(1j*np.angle(z).reshape(n,-1))).max()<2e-14
            # Bind every quantile node to the source marginal, not merely its
            # integrated energy. The independently integrated mean fixes scale.
            expected=np.sort(amplitude,axis=0)*training['normalization']
            rms=np.sqrt(np.mean(amplitude**2,axis=0))
            assert np.all(abs(profile['amplitude']-expected)<=1e-30+g['mean_power_relative']*rms)
            assert np.array_equal(profile['phase'],np.sort(phase,axis=0))
            assert abs(np.angle(np.exp(1j*(profile['fixed_phase']-np.angle(z.mean(axis=0)))))).max()<2e-13
            features=np.column_stack([amplitude,phase]);scores=np.zeros_like(features)
            for j in np.flatnonzero(profile['active']):
                values=features[:,j];order=sorted(range(n),key=lambda k:float(values[k]));rank=np.empty(n)
                first=0
                while first<n:
                    stop=first+1
                    while stop<n and values[order[stop]]==values[order[first]]:stop+=1
                    for k in order[first:stop]:rank[k]=(first+1+stop)/2
                    first=stop
                q=math.sqrt(2)*special.erfinv(2*(rank-.5)/n-1);q-=q.mean();scores[:,j]=q/math.sqrt(math.fsum(float(v*v) for v in q)/n)
            assert abs(scores-training['scores']).max()<2e-12
            basis=profile['basis'];pc=training['pc'];residual=training['residual']
            assert abs(pc@basis.T+residual-scores).max()<2e-12
            assert abs(np.sum(basis*basis,axis=1)+profile['residual_std']**2-profile['active']).max()<=g['unit_feature_variance_absolute']
            for values,expected in [(pc,profile['rho']),(residual,profile['residual_rho'])]:
                actual=[]
                for column in values.T:
                    denominator=math.fsum(float(v*v) for v in column[:-1])
                    r=math.fsum(float(v*w) for v,w in zip(column[:-1],column[1:]))/denominator if denominator>1e-20 else 0.
                    actual.append(max(-.95,min(.95,r)))
                assert abs(np.array(actual)-expected).max(initial=0)<2e-12
            if producer['stage']=='known':
                assert sha(folder/'known.wav')==row['wave_sha256']
                sparse_wave(profile,folder/'known.wav',64,plan['known_audio_seconds'],1,True)
                # Also verify the constant control against the old frozen C.
                if row['label']=='steady':
                    old=a.workspace/'baselines/coefficient_geometry_v1/evidence/known1/steady/C_seed1.wav'
                    first=sf.read(old,always_2d=True)[0][:48000]
                    second_audio=sf.read(folder/'known.wav',always_2d=True)[0]
                    bound=np.spacing(abs(first.astype('float32'))).astype(float)+g['independent_wave_absolute_FS']
                    assert np.all(abs(first-second_audio)<=bound)
            else:
                root=row['root_hz']
                for qmc_row in row['QMC']:
                    path=folder/f'QMC_{qmc_row["seed"]}.npz';assert sha(path)==qmc_row['arrays_sha256']
                    d=np.load(path);normal=math.sqrt(2)*special.erfinv(2*d['normal']-1)
                    k=len(profile['rho'])
                    features=normal[:,:k]@basis.T+normal[:,k:]*profile['residual_std']
                    amp,ph=arrays(profile,features,True)
                    check_moments(d,amp,ph,root,'joint_')
                    check_moments(d,amp,np.broadcast_to(profile['fixed_phase'],amp.shape),root,'fixed_')
                    assert np.array_equal(d['joint_power'],d['fixed_power']);report['QMC_cases']+=1
                for audio in row['audio']:
                    assert sha(folder/audio['file'])==audio['sha256']
                    if audio['variant']!='original':
                        sparse_wave(profile,folder/audio['file'],root,plan['audio']['seconds'],audio['seed'],audio['variant']=='joint_phase')
                for temporal in row.get('temporal',[]):
                    path=folder/f'temporal_{temporal["seed"]}.npz';assert sha(path)==temporal['sha256']
                    d=np.load(path)
                    frames=plan['audio']['seconds']*48000;count=int(np.floor((frames-1)*root/12000))+2
                    endpoint=state(profile,count,temporal['seed']);k=len(profile['rho'])
                    normal=endpoint[:,:k]@basis.T+endpoint[:,k:]*profile['residual_std']
                    amp,ph=arrays(profile,normal,True)
                    check_moments(d,amp,ph,root,'')
                    centered=d['power']-d['power'].mean(axis=0)
                    expected=np.array([[math.fsum(float(x*y) for x,y in zip(left,right))/(len(centered)-1)
                                        for right in centered[1:].T] for left in centered[:-1].T])
                    assert (abs(expected-d['lag1_covariance'])/np.outer(d['mean'],d['mean'])).max()<2e-9
                if 'block37_1024_maximum_PCM_error_FS' in row:
                    x=sf.read(folder/'joint_phase_block37.wav',always_2d=True)[0]
                    y=sf.read(folder/f'joint_phase_{plan["audio"]["seeds"][0]}.wav',always_2d=True)[0]
                    assert abs(x-y).max()<=g['block_wave_absolute_FS']
            report['cases'].append(dict(label=row['label'],quantiles_ranks_AR_and_generation_verified=True))
            save(a.out/'report.json',report);print('PASS independent radial/circular generation',row['label'],flush=True)
        report.update(result='independent_radial_copula_audit_passed',stage=producer['stage'],
                      producer_report_sha256=sha(a.study/'report.json'),auditor_sha256=sha(__file__),heard=False)
    except Exception as exc:
        report.update(result='failed',error=repr(exc));raise
    finally:save(a.out/'report.json',report)


if __name__=='__main__':main()
