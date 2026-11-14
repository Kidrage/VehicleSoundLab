"""Independent AR, inverse CDF and scalar OSC audit of relative-phase audio."""
import argparse
import math
import os
from pathlib import Path
import shutil
import sys
from research_archive_v1 import load, save, sha


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for n in ('workspace','study','out'):p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args();repo=Path(__file__).resolve().parents[1]
    for n in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):os.environ[n]='2'
    sys.path.insert(0,str(a.workspace/'tools/python_deps'))
    import numpy as np
    import soundfile as sf
    from scipy import special,signal
    a.out.mkdir(parents=True,exist_ok=False);shutil.copy2(__file__,a.out/'executed_audit.py')
    report=dict(result='running',cases=[],new_waves=0,maximum_sparse_wave_error_FS=0.,
                maximum_endpoint_moments_relative_error=0.)
    try:
        producer=load(a.study/'report.json');assert producer['result']=='relative_phase_paired_audio_ready'
        for n,h in producer['sources'].items():assert sha(repo/n)==sha(a.study/'exact_sources'/n)==h
        for n,h in producer['inputs'].items():assert sha(n)==h
        def inverse(table,normal):
            probability=.5+.5*special.erf(normal/math.sqrt(2));n=len(table)
            points=np.r_[0,(np.arange(n)+.5)/n,1]
            return np.column_stack([np.interp(probability[:,j],points,np.r_[table[0,j],table[:,j],table[-1,j]]) for j in range(table.shape[1])])
        def decode(model,normal):
            h=len(model['fixed_phase']);k=len(model['rho'])
            raw=np.einsum('nk,dk->nd',normal[:,:k],model['basis'],optimize=False)+normal[:,k:]*model['residual_std']
            amplitude=inverse(model['amplitude'],raw[:,:2*h]).reshape(len(raw),h,2)
            coordinate=inverse(model['phase'],raw[:,2*h:])
            return amplitude,np.stack([coordinate[:,:h]+coordinate[:,h:]/2,coordinate[:,:h]-coordinate[:,h:]/2],axis=-1)
        for row in producer['cases']:
            folder=a.study/row['label'];assert sha(folder/'profile.npz')==row['profile_sha256']
            model=dict(np.load(folder/'profile.npz'));root=row['root_hz'];rho=np.r_[model['rho'],model['residual_rho']]
            for seed in (1,23117,61927):
                clips=[r for r in row['audio'] if r['seed']==seed];count=clips[0]['texture_endpoints']
                noise=np.random.Generator(np.random.PCG64(seed)).standard_normal((count,len(rho)))
                state=np.empty_like(noise)
                for j,r in enumerate(rho):
                    scale=math.sqrt(1-r*r)
                    state[:,j]=signal.lfilter([scale],[1.,-r],noise[:,j],zi=[(1-scale)*noise[0,j]])[0]
                amp,phase=decode(model,state)
                descriptor=next(t for t in row['temporal'] if t['seed']==seed)
                path=folder/f'temporal_{seed}.npz';assert sha(path)==descriptor['sha256'];saved=np.load(path)
                power=[];hz=np.arange(1,len(model['fixed_phase'])+1)*root
                for lo,hi in [[3000,6000],[6000,8000],[8000,10000],[10000,14000]]:
                    mask=(hz>=lo)&(hz<hi)
                    for c in (0,1):power.append(np.sum(amp[:,mask,c]**2,axis=1)/2)
                power=np.array(power).T;mean=power.mean(axis=0);centered=power-mean
                cov=np.cov(power,rowvar=False,ddof=0)
                lag=np.einsum('ni,nj->ij',centered[:-1],centered[1:],optimize=False)/(len(power)-1)
                error=float((abs(power-saved['power'])/mean).max())
                assert error<2e-10 and (abs(cov-saved['covariance'])/np.outer(mean,mean)).max()<2e-10
                assert (abs(lag-saved['lag1_covariance'])/np.outer(mean,mean)).max()<2e-10
                report['maximum_endpoint_moments_relative_error']=max(report['maximum_endpoint_moments_relative_error'],error)
                frames=clips[0]['frames'];indices=np.unique(np.r_[np.linspace(0,frames-1,64).astype(int),0,1,36,37,187,188,1023,1024,1025])
                positions=indices*root/12000;at=positions.astype(int);u=positions-at
                raw=((1-u[:,None])*state[at]+u[:,None]*state[at+1])/np.sqrt((1-u[:,None])**2+u[:,None]**2+2*rho*u[:,None]*(1-u[:,None]))
                A,P=decode(model,raw)
                for clip in clips:
                    wave,sr=sf.read(folder/clip['file'],always_2d=True)
                    assert sha(folder/clip['file'])==clip['sha256'] and sr==48000 and wave.shape==(frames,2) and np.isfinite(wave).all()
                    angle=np.broadcast_to(model['fixed_phase'],P.shape) if clip['variant']=='fixed_phase' else P
                    wanted=[]
                    for sample,amplitude,phase in zip(indices,A,angle):
                        base=math.fmod(2*math.pi*float(sample)*root/48000,2*math.pi)
                        channel=[]
                        for c in (0,1):
                            terms=[]
                            for h in range(1,len(amplitude)+1):
                                x=max(0.,min(1.,(h*root-19200)/2400))
                                terms.append(amplitude[h-1,c]*(1-3*x*x+2*x*x*x)*math.cos(base*h+phase[h-1,c]))
                            channel.append(math.fsum(terms))
                        wanted.append(channel)
                    wanted=np.array(wanted);error=abs(wave[indices]-wanted)
                    bound=.5001*np.spacing(abs(wanted.astype('float32'))).astype(float)+2e-10
                    assert np.all(error<=bound),float((error-bound).max())
                    report['maximum_sparse_wave_error_FS']=max(report['maximum_sparse_wave_error_FS'],float(error.max()))
                    report['new_waves']+=1
            for clip in row.get('block37_copies',[]):
                wave=sf.read(folder/clip['file'],always_2d=True)[0]
                assert sha(folder/clip['file'])==clip['sha256']
                assert np.array_equal(wave,sf.read(folder/f'{clip["variant"]}_{clip["seed"]}.wav',always_2d=True)[0])
            report['cases'].append(dict(label=row['label'],state_time_and_scalar_OSC_verified=True))
        report.update(result='independent_relative_phase_audio_audit_passed',producer_sha256=sha(a.study/'report.json'),
                      auditor_sha256=sha(a.out/'executed_audit.py'),heard=False)
        save(a.out/'report.json',report);print(report['result'])
    except BaseException as exc:
        report.update(result='failed',error=repr(exc));save(a.out/'report.json',report);raise


if __name__=='__main__':main()
