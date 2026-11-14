"""Independent direct signed-lag sums and input regeneration, no new sound."""
import argparse,shutil,sys
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__)
for key in ['workspace','input','out']:p.add_argument('--'+key,type=Path,required=True)
a=p.parse_args();repo=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(a.workspace/'tools/python_deps'))
import numpy as np
import soundfile as sf
from scipy import signal,interpolate
from research_archive_v1 import load,save,sha

a.out.mkdir(parents=True,exist_ok=False);shutil.copy2(Path(__file__),a.out/'executed_auditor.py')
r=dict(result='running',input_report_sha256=sha(a.input/'report.json'),observations=[])
def direct(x,z,lags):
    n=len(x);origins=np.arange(96,n-96);base=x[origins]
    f=np.column_stack((z,z[:,1]*z[:,0].conj(),z[:,2]*z[:,0].conj(),z[:,2]*z[:,1].conj()))[origins]
    f=np.conj(f-f.mean(axis=0));out=[]
    for lag in lags:
        late=x[origins+lag]
        norm=np.sqrt(np.mean(abs(base)**2,axis=0)*np.mean(abs(late)**2,axis=0))
        # Direct time-domain products, not the observer's FFT correlation.
        out.append(np.stack([(late[:,b]*np.conj(base[:,b]))@f/len(origins)/norm[b]
            for b in range(x.shape[1])]))
    return np.array(out)
def independent_analytic(audio,sos):
    filtered=[]
    for sections in sos:
        y=audio[:,0].copy()
        for b0,b1,b2,a0,a1,a2 in sections:
            y=signal.lfilter([b0,b1,b2],[a0,a1,a2],y)
        spectrum=np.fft.fft(y);h=np.zeros(len(y));h[0]=h[len(y)//2]=1;h[1:len(y)//2]=2
        filtered.append(np.fft.ifft(spectrum*h)[12000:-12000])
    return np.column_stack(filtered)
try:
    report=load(a.input/'report.json');assert report['result']=='idle_signed_lag_structure_observed'
    for path,digest in report['inputs'].items():assert sha(path)==digest
    for name,digest in report['sources'].items():assert sha(repo/name)==digest==sha(a.input/'exact_sources'/name)
    with np.load(a.input/'known.npz') as f:
        x=f['x'];z=f['z'];c=f['c']
    err=float(abs(direct(x,z,np.arange(-96,97))-c).max());assert err<2e-13
    r['all193_known_direct_error']=err
    profile=load(a.workspace/'baselines/fixed_source_profiles_v1/evidence/trial1/F2_tailpipe/profile.json')
    generated=a.workspace/'baselines/idle_phase_recipe_v1/evidence/render2'
    model=load(generated/'model.json');splines={}
    for seed in [149921,277139,381611]:
        with np.load(generated/f'motion_{seed}.npz') as f:values=f['coordinate_nodes']
        nodes=(np.arange(len(values))-2)/model['node_rate']
        splines[seed]=interpolate.make_interp_spline(nodes,values,k=3,bc_type='natural')
    parent=a.workspace/'baselines/idle_conditioned_detail_v1/evidence/observe1'
    for row in report['observations']:
        path=a.input/row['file'];assert sha(path)==row['sha256']
        with np.load(path) as f:
            x=f['analytic'];z=f['phasors'];c=f['covariance'];sos=f['sos'];lags=f['lags']
        assert np.array_equal(lags,np.arange(-96,97)) and np.isfinite(c).all()
        if row['group'] in ['source','phase_control']:
            with np.load(parent/(row['part']+'.npz')) as f:audio=f['audio'];expected_z=f['phasors']
            if row['group']=='phase_control':
                spec=np.fft.rfft(audio,axis=0);random=np.random.Generator(np.random.PCG64(row['seed']))
                angle=random.uniform(-np.pi,np.pi,len(spec));angle[[0,-1]]=0.
                audio=np.fft.irfft(spec*np.exp(1j*angle[:,None]),n=len(audio),axis=0)
                with np.load(parent/f"{row['part']}_phase_{row['seed']}.npz") as f:expected_z=f['phasors']
            expected_z=expected_z[12000:-12000]
        else:
            meta=row['metadata'];audio,rate=sf.read(meta['input'],start=meta['start_frame'],frames=144000,always_2d=True)
            assert rate==48000
            t=np.arange(meta['start_frame']+12000,meta['start_frame']+132000)/48000
            if row['group']=='static':
                freq=np.asarray(profile['modal']['frequencies_hz'])[[1,2,4]]
                initial=np.asarray(profile['modal']['initial_phase_LR'])[[1,2,4],0]
                expected_z=np.exp(1j*(2*np.pi*t[:,None]*freq+initial))
            else:
                u=splines[row['seed']](t);phi=model['carrier_phase_rad']+2*np.pi*model['carrier_hz']*t
                constraints=np.array([[-1.,-1.,1.],[3.,-2.,0.],[2.,3.,5.]])
                theta=np.linalg.solve(constraints,np.column_stack((u,38*phi)).T).T
                expected_z=np.exp(1j*theta)
        phase_error=float(abs(expected_z-z).max());assert phase_error<2e-10,(row['label'],phase_error)
        regenerated=independent_analytic(audio,sos)
        wave_error=float(abs(regenerated-x).max());assert wave_error<2e-11,(row['label'],wave_error)
        chosen=lags if row['group']=='source' else np.array([-96,-48,-12,0,12,48,96])
        actual=direct(x,z,chosen);curve_error=float(abs(actual-c[chosen+96]).max())
        assert curve_error<2e-12,(row['label'],curve_error)
        r['observations'].append(dict(label=row['label'],input_sha256=row['sha256'],
            all193_direct_lags=row['group']=='source',direct_lags=chosen.tolist(),
            direct_curve_error=curve_error,independent_filter_analytic_error=wave_error,
            independent_phase_error=phase_error))
        save(a.out/'report.json',r);print(row['label'],flush=True)
    assert len(r['observations'])==32
    r.update(result='passed',all193_source_lags_direct=True,every_case7signed_lags_direct=True,
        all32_inputs_independent_filter_and_phase_regenerated=True,
        scope='Curve calculation and input regeneration only; not perceptual or physical-source qualification.')
except Exception as exc:r.update(result='failed',error=repr(exc));raise
finally:save(a.out/'report.json',r)
print(dict(result=r['result'],cases=len(r['observations'])),flush=True)
