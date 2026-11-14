"""All12 existing gain paths and native finite2/4-power joint uncertainty; no new streams."""
import argparse, os, shutil, sys
from pathlib import Path
parser=argparse.ArgumentParser(description=__doc__)
for key in ['workspace','out']:parser.add_argument('--'+key,type=Path,required=True)
args=parser.parse_args();repo=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(args.workspace/'tools/python_deps'))
for key in ['OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','OMP_NUM_THREADS']:os.environ[key]='2'
import numpy as np
from research_archive_v1 import load,save,sha
from accel_upper_am_v1.model import generate
from accel_gain_moments_v1.model import finite_moments,observed
from accel_gain_moments_v1.known import known

args.out.mkdir(parents=True,exist_ok=False)
r=dict(result='running',sources={},parent_files={},observations=[])
try:
    for name in ['tools/observe_accel_gain_moments_v1.py','tools/accel_gain_moments_v1/model.py','tools/accel_gain_moments_v1/known.py',
                 'tools/accel_upper_am_v1/model.py','tools/accel_upper_forward_v1/kernel.py','tools/research_archive_v1.py','research/accel_gain_moments_v1_plan.json']:
        dest=args.out/'exact_sources'/name;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(repo/name,dest);r['sources'][name]=sha(repo/name)
    r['known'],arrays=known();np.savez_compressed(args.out/'known.npz',**arrays);r['known_sha256']=sha(args.out/'known.npz')
    save(args.out/'report.json',r);print(dict(known=r['known']),flush=True)
    parent=args.workspace/'baselines/accel_upper_realization_v1'
    r['parent_manifest_sha256']=sha(parent/'manifest.json');table={v['path']:v['sha256'] for v in load(parent/'manifest.json')['files']}
    def read(name):
        path=parent/name;assert sha(path)==table[name];r['parent_files'][name]=table[name];return path
    previous=load(read('evidence/generate1/report.json'));assert load(read('evidence/audit1/report.json'))['result']=='passed'
    for row in previous['observations']:
        model_name='inputs/parent/'+row['model_parent_file']
        with np.load(read(model_name)) as model:
            L=model['L'];G=L@L.T;tau=float(model['parameters'][-1]);m=len(model['tile'])*480
            theory=finite_moments(G,tau,m);block=[];run=[]
            for record in row['records']:
                assert record['frames']==8*m
                warm=record['warmup_frames'];gain=generate(L,tau,record['frames']+warm,record['gain_seed'])['gain'][warm:]
                seen=observed(gain,m);block.append(seen['block']);run.append(seen['run'])
                np.testing.assert_allclose(seen['run'][:4],record['gain_squared_mean'],rtol=1e-12,atol=1e-14)
            block=np.array(block);run=np.array(run);mean=run.mean(axis=0);sd=np.sqrt(np.diag(theory['independent3_run_mean_covariance']))
            defined=sd>0;score=np.zeros_like(sd);score[defined]=(mean-theory['mean'])[defined]/sd[defined]
            file=args.out/(row['segment']+'_'+row['branch']+'.npz')
            np.savez_compressed(file,**theory,actual_block=block,actual_run=run,actual_mean=mean,pooled3_sd=sd,
                descriptive_standardized_difference=score,standardized_defined=defined,frames_per_block=m,tau=tau)
        r['observations'].append(dict(segment=row['segment'],branch=row['branch'],fit_available=row['fit_available'],model_parent_file=model_name,
            file=file.name,sha256=sha(file),records=row['records'],frames_per_block=m,tau=tau,
            expected=theory['mean'].tolist(),actual_mean=mean.tolist(),pooled3_sd=sd.tolist(),
            descriptive_standardized_difference=score.tolist(),standardized_defined=defined.tolist()))
        save(args.out/'report.json',r);print(dict(segment=row['segment'],branch=row['branch'],g4_expected=theory['mean'][4:].tolist(),
            g4_actual=mean[4:].tolist(),g4_pooled3_sd=sd[4:].tolist()),flush=True)
    assert len(r['observations'])==12
    r.update(result='all12_native_gain_power_moments_and_existing_paths_complete',cases=12,continuous_runs=36,blocks=288,
             moment_coordinates=8,all_block_covariances=True,new_seeds=False,new_audio=False,
             not_VarS_or_conditional_quadratic_uncertainty=True,not_Gaussian_scores_or_confidence_intervals=True)
except Exception as exc:r.update(result='failed',error=repr(exc));raise
finally:save(args.out/'report.json',r)
print(dict(result=r['result']),flush=True)
