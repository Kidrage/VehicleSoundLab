"""Independent all-native QR, signed covariance and periodogram checks for new candidates."""
import argparse,os,shutil,sys
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__)
for key in ['workspace','render','input','out']:p.add_argument('--'+key,type=Path,required=True)
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
r=dict(result='running',input_sha256=sha(a.input/'report.json'),errors={},window_QR=0,global_QR=0,groups=[],reused_files_checked=0)


def check(key,x,y,gate=1e-10,relative=0):
    x=np.asarray(x);y=np.asarray(y);d=float(abs(x-y).max());r['errors'][key]=max(d,r['errors'].get(key,0.))
    assert d<=gate+relative*float(abs(y).max()),(key,d)


def stats(c,reference,f,row):
    vectors=[]
    for j in range(3):
        z=c[:,j,[1,2,4]]/reference;vectors.append(np.column_stack((z.real,z.imag)))
    matrices={key:covariance(vectors[i],vectors[j]) for key,i,j in [('covariance',0,0),('main_covariance',1,1),
        ('detail_covariance',2,2),('main_detail_covariance',1,2),('detail_main_covariance',2,1)]}
    matrices['cross_covariance']=matrices['main_detail_covariance']+matrices['detail_main_covariance']
    for key,value in matrices.items():check('all51_signed_'+key,value,f[key],1e-9)
    check('signed_sum',matrices['covariance'],matrices['main_covariance']+matrices['detail_covariance']+matrices['cross_covariance'],1e-9)
    for key,bus in [('std','covariance'),('main_std','main_covariance'),('detail_std','detail_covariance')]:check(key,np.sqrt(np.diag(matrices[bus][25])),row[key],1e-9)
    fractions=np.array([np.diag(matrices[k][25])/np.diag(matrices['covariance'][25]) for k in ['main_covariance','detail_covariance','cross_covariance']])
    check('signed_fractions',fractions,row['lag0_signed_variance_ratios'],1e-8,2e-7)
    x=vectors[0]-vectors[0].mean(axis=0);n=len(x)
    hz,p=signal.periodogram(x,fs=50,window=np.hanning(n+1)[:-1],detrend=False,scaling='density',axis=0);p*=50/n
    check('temporal_PSD',p,f['temporal_psd'])
    powers=np.array([p[(hz>=lo)&(hz<hi)].sum(axis=0) for lo,hi in [[0,1],[1,3],[3,8],[8,25.000001]]]);check('temporal_bands',powers,f['temporal_power'])
    check('rho',np.array([np.diag(matrices['covariance'][25+k])/np.diag(matrices['covariance'][25]) for k in [5,10,25]]),f['rho_100_200_500ms'],1e-8)


try:
    run=load(a.input/'report.json');assert run['result']=='complete_actual_complex75_three_aperture_observation'
    for path,digest in run['sources'].items():assert sha(a.input/'exact_sources'/path)==digest
    for path,digest in run['inputs'].items():assert sha(path)==digest
    reused=Path(run['reuse']['root']);assert sha(reused/'report.json')==run['reuse']['report_sha256']
    for row in run['reuse']['cases']+run['reuse']['spectra']:
        assert sha(reused/row['file'])==row['sha256'];r['reused_files_checked']+=1
    root=a.workspace/'baselines';freq=np.array(load(root/'fixed_source_profiles_v1/evidence/trial1/F2_tailpipe/profile.json')['modal']['frequencies_hz'])
    render=load(a.render/'report.json');phase_root=root/'idle_phase_recipe_v1/evidence/render2';pm=load(phase_root/'model.json')
    for row in render['renders']:
        seed=row['seed']
        with np.load(phase_root/f'motion_{seed}.npz') as f:motion=spline(pm,f['coordinate_nodes'])
        for branch in ['independent_old','complex75']:
            wave={bus:sf.read(a.render/row['files'][branch+'_'+bus]['file'],always_2d=True)[0][:,0] for bus in ['mix','main']}
            for block,start in enumerate(range(0,1152000,144000)):
                mix=wave['mix'][start:start+144000];main=wave['main'][start:start+144000];buses=np.column_stack((mix,main,mix-main))
                for basis in ['procedural','measured_acoustic']:
                    label=f'{branch}_{seed}_{block}_{basis}'
                    z=phasors(pm,motion,np.arange(start,start+144000)/48000) if basis=='procedural' else measured(mix,freq)
                    A=design(len(mix),freq,z)
                    rows=[v for v in run['cases'] if v['label']==label];assert len(rows)==3
                    for item in rows:
                        path=a.input/item['file'];assert sha(path)==item['sha256'];c=coefficient(buses,A,item['window_ms']);r['window_QR']+=116
                        with np.load(path) as f:
                            check('all288_native_QR',c,f['coefficients']);check('bus_identity',c[:,0],c[:,1]+c[:,2]);stats(c,f['reference'],f,item)
                    item=next(v for v in run['spectra'] if v['label']==label);path=a.input/item['file'];assert sha(path)==item['sha256']
                    residual,beta=project(buses,A);s=spectral(buses,residual,z);r['global_QR']+=1
                    with np.load(path) as f:
                        check('all96_global_QR',beta,f['beta'])
                        for key,value in s.items():check('all96_periodogram_'+key,value,f[key]);check('spectral_report_'+key,value,item['summary'][key])
                    r['groups'].append(label);save(a.out/'report.json',r)
            print(dict(seed=seed,branch=branch,groups=len(r['groups'])),flush=True)
    assert r['window_QR']==33408 and r['global_QR']==96 and len(r['groups'])==96 and r['reused_files_checked']==224
    r.update(result='passed',actual_new_multibus_cases=288,all51signed6x6_covariances=True,all96native_spectra=True,phase_estimator_included=True,
        baseline_source_observations_hash_reused=True,listening_accepted=False)
except Exception as exc:r.update(result='failed',error=repr(exc));raise
finally:save(a.out/'report.json',r)
print(dict(result=r['result'],errors=r['errors'],window_QR=r['window_QR'],global_QR=r['global_QR']),flush=True)
