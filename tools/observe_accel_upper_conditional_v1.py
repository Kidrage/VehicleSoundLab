"""Condition on all existing gains, retaining exact realization and unconditional-mean residuals."""
import argparse,os,shutil,sys
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__)
for key in ['workspace','out']:p.add_argument('--'+key,type=Path,required=True)
a=p.parse_args();repo=Path(__file__).resolve().parents[1];sys.path.insert(0,str(a.workspace/'tools/python_deps'))
for key in ['OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','OMP_NUM_THREADS']:os.environ[key]='2'
import numpy as np
from research_archive_v1 import load,save,sha
from accel_upper_am_v1.model import generate
from accel_upper_conditional_v1.model import conditional_mean
from accel_upper_conditional_v1.known import known

a.out.mkdir(parents=True,exist_ok=False);r=dict(result='running',sources={},parent_files={},observations=[],blocks=0)
try:
    for name in ['tools/observe_accel_upper_conditional_v1.py','tools/accel_upper_conditional_v1/model.py','tools/accel_upper_conditional_v1/known.py',
                 'tools/accel_upper_am_v1/model.py','tools/accel_upper_forward_v1/kernel.py','tools/research_archive_v1.py','research/accel_upper_conditional_v1_plan.json']:
        dest=a.out/'exact_sources'/name;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(repo/name,dest);r['sources'][name]=sha(repo/name)
    r['known'],arrays=known();np.savez_compressed(a.out/'known.npz',**arrays);r['known_sha256']=sha(a.out/'known.npz');save(a.out/'report.json',r);print(dict(known=r['known']),flush=True)
    parent=a.workspace/'baselines/accel_upper_realization_v1';r['parent_manifest_sha256']=sha(parent/'manifest.json');table={v['path']:v['sha256'] for v in load(parent/'manifest.json')['files']}
    def read(name):
        path=parent/name;assert sha(path)==table[name];r['parent_files'][name]=table[name];return path
    previous=load(read('evidence/generate1/report.json'));assert load(read('evidence/audit1/report.json'))['result']=='passed'
    for row in previous['observations']:
        model_name='inputs/parent/'+row['model_parent_file'];carrier_name='inputs/parent/'+row['carrier_parent_file'];paths=[];carriers=[];totals=[];actuals=[];window_terms=[];group_terms=[];squared_means=[]
        with np.load(read(model_name)) as model,np.load(read(carrier_name)) as carrier:
            R=carrier['covariance'][len(carrier['impulse'])-1:][:,[0,1,2,3],[0,1,2,3]];P=R[0];tile=model['tile'];frames=len(tile)*480
            expected=model['prediction'][5].diagonal();target=model['target'][5].diagonal()
            for record in row['records']:
                motion=generate(model['L'],float(model['parameters'][-1]),record['frames']+record['warmup_frames'],record['gain_seed']);gain=motion['gain'][record['warmup_frames']:]
                squared_mean=np.mean(gain**2,axis=0);assert abs(squared_mean-record['gain_squared_mean']).max()<1e-12;squared_means.append(squared_mean)
                values=[conditional_mean(gain[b*frames:(b+1)*frames],R,tile,P) for b in range(8)]
                paths.append([v['path'] for v in values]);carriers.append([v['carrier'] for v in values]);totals.append([v['total'] for v in values])
                window_terms.append([v['window_quadratic'] for v in values]);group_terms.append([v['group_correction'] for v in values])
                obs_name='evidence/generate1/'+record['observation_file']
                with np.load(read(obs_name)) as obs:actuals.append(obs['raw_theoretical_normalized'][:,5].diagonal(axis1=1,axis2=2))
                r['blocks']+=8
            path=np.array(paths);noise=np.array(carriers);conditional=np.array(totals);actual=np.array(actuals)
            file=a.out/(row['segment']+'_'+row['branch']+'.npz')
            np.savez_compressed(file,path=path,carrier=noise,conditional=conditional,actual=actual,expected=expected,source_target=target,
                gain_path_effect=conditional-expected,carrier_realization_effect=actual-conditional,total_effect=actual-expected,
                window_quadratic=np.array(window_terms),group_correction=np.array(group_terms),squared_gain_means=np.array(squared_means),tile=tile,power=P)
        r['observations'].append(dict(segment=row['segment'],branch=row['branch'],fit_available=row['fit_available'],model_parent_file=model_name,carrier_parent_file=carrier_name,
            file=file.name,sha256=sha(file),records=row['records'],actual_mean=actual.mean(axis=(0,1)).tolist(),conditional_mean=conditional.mean(axis=(0,1)).tolist(),
            expected=expected.tolist(),mean_gain_path_effect=(conditional-expected).mean(axis=(0,1)).tolist(),
            mean_carrier_realization_effect=(actual-conditional).mean(axis=(0,1)).tolist()))
        save(a.out/'report.json',r);print(dict(segment=row['segment'],branch=row['branch'],mean_path_effect=r['observations'][-1]['mean_gain_path_effect'],
            mean_carrier_effect=r['observations'][-1]['mean_carrier_realization_effect']),flush=True)
    assert len(r['observations'])==12 and r['blocks']==288;r.update(result='all12_fixed_gain_conditional_means_complete',new_generation_seeds=False,
        new_listening_audio=False,conditional_mean_not_variance_qualification=True,only_zero_lag_diagonal=True,pre_refilter_only=True)
except Exception as exc:r.update(result='failed',error=repr(exc));raise
finally:save(a.out/'report.json',r)
print(dict(result=r['result'],blocks=r['blocks']),flush=True)
