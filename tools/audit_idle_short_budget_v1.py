"""Verify all24s actual bus responsibility and all source baseband residual observations."""
import argparse,os,shutil,sys
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__)
for key in ['workspace','input','out']:p.add_argument('--'+key,type=Path,required=True)
a=p.parse_args();repo=Path(__file__).resolve().parents[1];sys.path.insert(0,str(a.workspace/'tools/python_deps'))
for key in ['OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','OMP_NUM_THREADS']:os.environ[key]='2'
import numpy as np
import soundfile as sf
from scipy import signal
from research_archive_v1 import load,save,sha
from idle_short_budget_v1.independent import measured,design,coefficient,project,covariance,spectral
from idle_phase_recipe_v1.phase import spline,phasors

a.out.mkdir(parents=True,exist_ok=False);shutil.copy2(__file__,a.out/'executed_auditor.py')
shutil.copy2(repo/'tools/idle_short_budget_v1/independent.py',a.out/'executed_independent.py')
r=dict(result='running',input_sha256=sha(a.input/'report.json'),cases=[],spectra=[],errors={},window_QR=0,global_QR=0,known_global_QR=0)


def check(key,x,y,gate=1e-10,relative=0):
    x=np.asarray(x);y=np.asarray(y);d=float(abs(x-y).max());r['errors'][key]=max(d,r['errors'].get(key,0.))
    assert d<=gate+relative*float(abs(y).max()),(key,d)


def vector(c,ref):
    z=c[:,[1,2,4]]/ref;return np.column_stack((z.real,z.imag))


def verify_stats(c,reference,f,row):
    if c.ndim==2:c=c[:,None,:]
    v=[vector(c[:,j],reference) for j in range(c.shape[1])]
    cov=covariance(v[0],v[0]);check('all168_covariance',cov,f['covariance'],1e-9)
    check('all168_std',np.sqrt(np.diag(cov[25])),f['std'],1e-9)
    x=v[0]-v[0].mean(axis=0);hz,p=signal.periodogram(x,fs=50,window=np.hanning(len(x)+1)[:-1],axis=0,detrend=False,scaling='density')
    check('all168_temporalPSD',p*50/len(x),f['temporal_psd'])
    if len(v)==3:
        matrices=dict(main_covariance=covariance(v[1],v[1]),detail_covariance=covariance(v[2],v[2]),
            main_detail_covariance=covariance(v[1],v[2]),detail_main_covariance=covariance(v[2],v[1]))
        matrices['cross_covariance']=matrices['main_detail_covariance']+matrices['detail_main_covariance']
        for key,value in matrices.items():check('all144_'+key,value,f[key],1e-9)
        check('all144_coefficient_sum',c[:,0],c[:,1]+c[:,2])
        check('all144_signed_budget_sum',cov,matrices['main_covariance']+matrices['detail_covariance']+matrices['cross_covariance'],1e-9)
        for name,key in [('main_std','main_covariance'),('detail_std','detail_covariance')]:check('all144_'+name,np.sqrt(np.diag(matrices[key][25])),row[name],1e-9)
        ratios=np.array([np.diag(matrices[key][25])/np.diag(cov[25]) for key in ['main_covariance','detail_covariance','cross_covariance']])
        check('all144_signed_ratios',ratios,row['lag0_signed_variance_ratios'],1e-8,2e-7)


try:
    run=load(a.input/'report.json');assert run['result']=='complete_idle_short_bus_and_near75_budget_observed'
    for path,digest in run['sources'].items():assert sha(a.input/'exact_sources'/path)==digest
    for path,digest in run['inputs'].items():assert sha(path)==digest
    root=a.workspace/'baselines';freq=np.array(load(root/'fixed_source_profiles_v1/evidence/trial1/F2_tailpipe/profile.json')['modal']['frequencies_hz'])
    with np.load(a.input/'known_aperture.npz') as f:
        A=design(len(f['buses']),freq,f['phasors'])
        for ms in [50,100,200]:
            c=coefficient(f['buses'],A,ms);check('known_all3_multibus_FM',c,np.broadcast_to(f['expected'],c.shape));r['window_QR']+=116
    with np.load(a.input/'known_budget.npz') as f:
        for key in ['main','detail','mix']:
            check('known_negative_cross_'+key,covariance(f[key],f[key]),f[{'main':'main_covariance','detail':'detail_covariance','mix':'total_covariance'}[key]],1e-12)
        check('known_negative_cross',covariance(f['main'],f['detail'])+covariance(f['detail'],f['main']),f['cross_covariance'],1e-12)
    with np.load(a.input/'known_spectral.npz') as f:
        A=design(len(f['audio']),freq,f['phasors']);residual,beta=project(f['audio'],A);r['known_global_QR']+=1
        check('known_global_projection',residual,f['residual'],1e-12)
        y=(f['sideband_residual']*f['sideband_phasor'].conj())[12000:-12000];n=len(y);w=np.hanning(n+1)[:-1]
        # Scalar direct DFT at centre and its two Hann neighbours for each sideband.
        powers=[]
        for sign in [-1,1]:
            values=[np.dot(y*w,np.exp(-2j*np.pi*(sign*7.2+offset)*np.arange(n)/48000)) for offset in [-.4,0,.4]]
            powers.append(float(np.sum(abs(np.array(values))**2)/(n*np.dot(w,w))))
        check('known_signed_sideband_directDFT',powers,[.2**2/16]*2,1e-12)
        # Required non-separation AM counterexample is completed here before real-data audit.
        # The observation host checked the neighbour counterexample and demod AM power,
        # but did not project this AM control; record that timing explicitly.
        t=np.arange(len(A))/48000;am=(.02*A[:,1]*np.cos(2*np.pi*7.2*t))[:,None];leftover,_=project(am,A);r['known_global_QR']+=1
        am_rms=float(np.sqrt(np.mean(leftover[12000:-12000]**2)));assert am_rms>.003
        r['known_AM_projection_surviving_rms']=am_rms
        r['AM_projection_counterexample_timing']='Added in independent audit before real-data audit, NOT executed before original source observation. Original data/gates unchanged; no source fit or audio promotion.'
    oldroot=root/'idle_variation_budget_v1/evidence/observe1';old={row['label']:row for row in load(oldroot/'report.json')['cases']}
    sourceold=root/'idle_window_transfer_v1/evidence/observe1';cache={};wavecache={}
    render_root=root/'idle_local_partition_v1/evidence/render1';renders={row['seed']:row for row in load(render_root/'report.json')['renders']}
    phase_root=root/'idle_phase_recipe_v1/evidence/render2';phase_model=load(phase_root/'model.json');motions={}
    def material(label,meta):
        if label in cache:return cache[label]
        if meta['kind']=='generated':
            seed=meta['seed']
            if seed not in wavecache:
                wavecache[seed]={}
                for bus in ['mix','main']:
                    x,rate=sf.read(render_root/renders[seed]['files'][bus+'_1.0']['file'],always_2d=True);assert rate==48000;wavecache[seed][bus]=x[:,0]
                with np.load(phase_root/f'motion_{seed}.npz') as f:motions[seed]=spline(phase_model,f['coordinate_nodes'])
            start=meta['first_frame'];mix=wavecache[seed]['mix'][start:start+144000];main=wavecache[seed]['main'][start:start+144000]
            buses=np.column_stack((mix,main,mix-main))
            z=phasors(phase_model,motions[seed],np.arange(start,start+144000)/48000) if meta['phase_basis']=='procedural' else measured(mix,freq)
        else:
            origin=root/'idle_conditioned_detail_v1/evidence/observe1'
            with np.load(origin/(meta['part']+'.npz')) as f:audio=f['audio'][:,0];z=f['phasors']
            if meta['seed'] is not None:
                amplitude=np.fft.rfft(audio);p=np.random.default_rng(meta['seed']).uniform(-np.pi,np.pi,len(amplitude));p[0]=p[-1]=0
                audio=np.fft.irfft(amplitude*np.exp(1j*p),n=len(audio))
                with np.load(origin/f'{meta["part"]}_phase_{meta["seed"]}.npz') as f:z=f['phasors']
            buses=audio[:,None]
        cache[label]=(buses,z,design(len(buses),freq,z));return cache[label]
    for row in run['cases']:
        file=a.input/row['file'];assert sha(file)==row['sha256'];meta=row['metadata'];label=row['label']
        with np.load(file) as f:
            if row.get('reused_independently_audited_source'):
                assert sha(file)==sha(sourceold/row['file']);c=f['coefficients']
            else:
                buses,z,A=material(label,meta);c=coefficient(buses,A,row['window_ms']);r['window_QR']+=116
                check('all144_new_bus_QR',c,f['coefficients'])
                if row['window_ms']==200:
                    original=old[f'generated_{meta["seed"]}_1.0_{meta["block"]}_{meta["phase_basis"]}']
                    with np.load(oldroot/original['file']) as g:check('all48_original200ms_threebuses',c,g['coefficients'])
            verify_stats(c,f['reference'],f,row)
        r['cases'].append(dict(label=label,window_ms=row['window_ms']));save(a.out/'report.json',r)
    for row in run['spectra']:
        file=a.input/row['file'];assert sha(file)==row['sha256'];buses,z,A=material(row['label'],row['metadata'])
        residual,beta=project(buses,A);r['global_QR']+=1;result=spectral(buses,residual,z)
        with np.load(file) as f:
            check('all56_native_global_QR',beta,f['beta'])
            for key,value in result.items():
                check('all56_periodogram_'+key,value,f[key],1e-10);check('all56_report_'+key,value,row['summary'][key],1e-10)
        r['spectra'].append(row['label']);save(a.out/'report.json',r)
    assert r['window_QR']==17052 and r['global_QR']==56 and len(r['cases'])==168 and len(r['spectra'])==56
    r.update(result='all_idle_short_buses_and_native_residual_spectra_independently_checked',source_reused_windows=24,new_audio=False,new_fit=False)
except Exception as exc:r.update(result='failed',error=repr(exc));raise
finally:save(a.out/'report.json',r)
print(dict(result=r['result'],windowQR=r['window_QR'],globalQR=r['global_QR'],errors=r['errors']),flush=True)
