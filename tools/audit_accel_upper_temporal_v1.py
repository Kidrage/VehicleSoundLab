"""Independent FFT transfer, scalar finite statistics and full-bin phase checks."""
import argparse,math,shutil,sys
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__)
for key in ['workspace','input','out']:p.add_argument('--'+key,type=Path,required=True)
a=p.parse_args();repo=Path(__file__).resolve().parents[1];sys.path.insert(0,str(a.workspace/'tools/python_deps'))
import numpy as np
from research_archive_v1 import load,save,sha


def close(actual,expected,tol):
    error=float(abs(np.array(actual)-np.array(expected)).max(initial=0));assert error<tol,(error,tol);return error


def transfer(sos,length):
    z=np.exp(-2j*np.pi*np.arange(length//2+1)/length);result=np.ones(len(z),complex)
    for b0,b1,b2,a0,a1,a2 in sos:result*=(b0+b1*z+b2*z*z)/(a0+a1*z+a2*z*z)
    return result


def check(path,actual):
    z=np.load(path);x=z['audio'];filtered=z['filtered'];n=len(filtered);count=n//480
    assert actual['energy_windows']==count and filtered.shape==(len(x)-9600,2)
    length=1<<int(math.ceil(math.log2(len(x)+131072)))
    error=0.;moment_error=0.
    for b,sos in enumerate(z['sos']):
        y=np.fft.irfft(np.fft.rfft(x[:,0],n=length)*transfer(sos,length),n=length)[:len(x)][4800:-4800]
        error=max(error,close(y,filtered[:,b],1e-11))
        mean=math.fsum(filtered[:,b])/n;values=[float(t)-mean for t in filtered[:,b]]
        second=math.fsum(v*v for v in values)/n;fourth=math.fsum(v**4 for v in values)/n
        for key,value in [('variance',second),('cumulant4',fourth-3*second*second),('excess',fourth/second**2-3),
                          ('skew',math.fsum(v**3 for v in values)/n/second**1.5)]:
            moment_error=max(moment_error,close(value,actual['moments'][key][b],1e-10))
    power=np.array([[math.fsum(float(v)**2 for v in filtered[j*480:(j+1)*480,b])/480 for b in range(2)] for j in range(count)])
    close(power,z['power'],1e-18)
    means=np.array([math.fsum(power[:,b])/count for b in range(2)])
    covariance=np.array([[math.fsum((float(v[b])-means[b])*(float(v[c])-means[c]) for v in power)/count for c in range(2)] for b in range(2)])
    close(np.sqrt(covariance.diagonal())/means,actual['energy_CV'],1e-11)
    close(covariance/np.outer(means,means),actual['normalized_energy_covariance'],1e-11)
    close(covariance/np.sqrt(np.outer(covariance.diagonal(),covariance.diagonal())),actual['energy_correlation'],1e-11)
    return dict(filter_error=error,moment_error=moment_error)


a.out.mkdir(parents=True,exist_ok=False);shutil.copy2(__file__,a.out/'executed_auditor.py')
r=dict(result='running',observations=0,maximum_filter_error=0.,maximum_moment_error=0.,maximum_phase_spectrum_relative_error=0.)
try:
    report=load(a.input/'report.json');assert report['result']=='all3_passages_and9_phase_controls_observed'
    for name,digest in report['sources'].items():assert sha(repo/name)==digest==sha(a.input/'exact_sources'/name)
    parent=a.workspace/'baselines/accel_candidate_prediction_v1';assert sha(parent/'manifest.json')==report['parent_manifest_sha256']
    table={v['path']:v['sha256'] for v in load(parent/'manifest.json')['files']}
    for name,digest in report['parent_files'].items():assert sha(parent/name)==digest==table[name]
    for row in report['observations']:
        folder=a.input/row['segment'];original=np.load(folder/'original.npz')['audio']
        inputs=[np.load(parent/f"evidence/observe1/{row['segment']}/native_{i:02d}.npz")['audio'] for i in range(len(original)//12000)]
        assert np.array_equal(original,np.concatenate(inputs))
        fft=np.fft.rfft(original,axis=0)
        values=[(folder/'original.npz',row['original'])]+[(folder/f"phase_{v['seed']}.npz",v['statistics']) for v in row['controls']]
        assert [v['seed'] for v in row['controls']]==[149921,277139,381611]
        for path,stats in values:
            out=check(path,stats);r['observations']+=1;r['maximum_filter_error']=max(r['maximum_filter_error'],out['filter_error'])
            r['maximum_moment_error']=max(r['maximum_moment_error'],out['moment_error'])
            if path.name.startswith('phase_'):
                z=np.load(path);phase=z['phase'];assert phase[0]==phase[-1]==0.
                seed=int(path.stem.split('_')[1]);expected=np.random.default_rng(seed).uniform(-np.pi,np.pi,len(phase));expected[0]=expected[-1]=0.
                assert np.array_equal(phase,expected)
                # Direct cos/sin construction, independent of complex multiplication in observer.
                cosine,sine=np.cos(phase)[:,None],np.sin(phase)[:,None]
                rotated=(fft.real*cosine-fft.imag*sine)+1j*(fft.real*sine+fft.imag*cosine)
                close(np.fft.irfft(rotated,n=len(original),axis=0),z['audio'],1e-12)
                actual=np.fft.rfft(z['audio'],axis=0)
                error=close(abs(actual)/max(abs(fft).max(),1.),abs(fft)/max(abs(fft).max(),1.),1e-12)
                cross=fft[:,0]*np.conj(fft[:,1]);other=actual[:,0]*np.conj(actual[:,1]);error=max(error,close(other/max(abs(cross).max(),1.),cross/max(abs(cross).max(),1.),1e-12))
                r['maximum_phase_spectrum_relative_error']=max(r['maximum_phase_spectrum_relative_error'],error)
    assert r['observations']==12
    r.update(result='all12_temporal_observations_independently_verified',input_report_sha256=sha(a.input/'report.json'),
             same_recording_not_source_identity_or_new_generator=True)
except Exception as exc:r.update(result='failed',error=repr(exc));raise
finally:save(a.out/'report.json',r)
print(r,flush=True)
