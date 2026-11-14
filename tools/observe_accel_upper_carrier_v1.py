"""Compile every source matrix carrier and separate post-gain, refilter and stereo budgets."""
import argparse,os,shutil,sys
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__)
for key in ['workspace','out']:p.add_argument('--'+key,type=Path,required=True)
a=p.parse_args();repo=Path(__file__).resolve().parents[1];sys.path.insert(0,str(a.workspace/'tools/python_deps'))
for key in ['OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','OMP_NUM_THREADS']:os.environ[key]='2'
import numpy as np
from scipy import signal
from research_archive_v1 import load,save,sha
from accel_upper_carrier_v1.spectral import measure,factor,covariance,density,apply_gain,refilter,summaries
from accel_upper_carrier_v1.known import known,psd

a.out.mkdir(parents=True,exist_ok=False);r=dict(result='running',sources={},parents={},observations=[],native_windows=0)
try:
    for name in ['tools/observe_accel_upper_carrier_v1.py','tools/accel_upper_carrier_v1/spectral.py','tools/accel_upper_carrier_v1/known.py',
                 'tools/research_archive_v1.py','research/accel_upper_carrier_v1_plan.json']:
        dest=a.out/'exact_sources'/name;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(repo/name,dest);r['sources'][name]=sha(repo/name)
    r['known'],arrays=known();np.savez_compressed(a.out/'known.npz',**arrays);r['known_sha256']=sha(a.out/'known.npz');save(a.out/'report.json',r)
    print(dict(known=r['known']),flush=True)
    roots={}
    for key,stage in [('raw','accel_upper_joint_v1'),('gain','accel_upper_am_v1')]:
        root=a.workspace/'baselines'/stage;roots[key]=root;r['parents'][key]=dict(stage=stage,manifest_sha256=sha(root/'manifest.json'),files={})
    def read(key,name):
        root=roots[key];table={v['path']:v['sha256'] for v in load(root/'manifest.json')['files']};path=root/name
        assert sha(path)==table[name];r['parents'][key]['files'][name]=table[name];return path
    raw=load(read('raw','evidence/observe1/report.json'));gain=load(read('gain','evidence/fit1/report.json'))
    assert load(read('raw','evidence/audit1/report.json'))['result']=='passed'
    assert load(read('gain','evidence/audit1/report.json'))['result']=='passed'
    for row in raw['observations']:
        control=next(v for v in gain['observations'] if v['segment']==row['segment'] and v['branch']==row['branch'])
        with np.load(read('raw','evidence/observe1/'+row['file'])) as f:audio=f['filtered'];sos=f['sos']
        with np.load(read('gain','evidence/fit1/'+control['file'])) as f:Gamma=f['Gamma'];tau=float(f['parameters'][-1])
        target,starts=measure(audio);h,meta=factor(target,12000);lags,R=covariance(h);Rg=apply_gain(lags,R,Gamma,tau)
        unit=np.zeros(8192);unit[0]=1;q=np.column_stack([signal.sosfilt(s,unit) for s in sos for ch in range(2)])
        lf,Rf=refilter(lags,R,q);lf2,Rfg=refilter(lags,Rg,q);assert np.array_equal(lf,lf2)
        grid=psd(h,12000);grid_error=float(abs(grid-target).max()/abs(target).max());assert grid_error<1e-11
        power_error=float(abs(np.diag(Rg[11999])-np.diag(R[11999])).max()/abs(R[11999]).max());assert power_error<1e-12
        values=dict(target=target,compiled_grid=grid,Welch_carrier=density(lags,R,12000,12000),Welch_gain=density(lags,Rg,12000,12000),
                    Welch_refilter_carrier=density(lf,Rf,12000,12000),Welch_refilter_gain=density(lf,Rfg,12000,12000))
        file=a.out/(row['segment']+'_'+row['branch']+'.npz')
        np.savez_compressed(file,starts=starts,sos=sos,Gamma=Gamma,tau=tau,impulse=h,q=q,lags=lags,covariance=R,gain_covariance=Rg,**values)
        summaries_by_name={name:summaries(C,12000) for name,C in values.items()}
        r['observations'].append(dict(segment=row['segment'],branch=row['branch'],source_parent_file='evidence/observe1/'+row['file'],
            gain_parent_file='evidence/fit1/'+control['file'],file=file.name,sha256=sha(file),frames=len(audio),windows=len(starts),
            gain_fit_available=control['fit']['available'],factor=meta,grid_relative_error=grid_error,exact_variance_error=power_error,
            summaries=summaries_by_name))
        r['native_windows']+=len(starts);save(a.out/'report.json',r)
        print(dict(segment=row['segment'],branch=row['branch'],windows=len(starts),grid_error=grid_error),flush=True)
    assert len(r['observations'])==12 and r['native_windows']==348
    r.update(result='all12_source_carriers_and_gain_budgets_complete',new_listening_audio=False,new_runtime_profile=False,runtime_changed=False,
             unchanged_gain_parameters=True,unavailable_controls_not_promoted=True)
except Exception as exc:r.update(result='failed',error=repr(exc));raise
finally:save(a.out/'report.json',r)
print(dict(result=r['result'],windows=r['native_windows']),flush=True)
