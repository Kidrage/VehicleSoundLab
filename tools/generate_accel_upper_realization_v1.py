"""Generate every frozen matrix carrier with joint gains continuously, then observe all original-length blocks."""
import argparse,os,shutil,sys
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__)
for key in ['workspace','out']:p.add_argument('--'+key,type=Path,required=True)
a=p.parse_args();repo=Path(__file__).resolve().parents[1];sys.path.insert(0,str(a.workspace/'tools/python_deps'))
for key in ['OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','OMP_NUM_THREADS']:os.environ[key]='2'
import numpy as np
from scipy import signal
from research_archive_v1 import load,save,sha
from accel_upper_coloured_v1.model import generate_carrier
from accel_upper_am_v1.model import generate
from accel_upper_realization_v1.known import known
from accel_upper_realization_v1.observe import observe_run

SEEDS=[(464437,137591),(606181,286049),(780991,471217)];BLOCKS=8
a.out.mkdir(parents=True,exist_ok=False);r=dict(result='running',sources={},parent_files={},observations=[],records=0,blocks_observed=0,seed_pairs=SEEDS,continuous_blocks=BLOCKS)
try:
    for name in ['tools/generate_accel_upper_realization_v1.py','tools/accel_upper_realization_v1/observe.py','tools/accel_upper_realization_v1/known.py',
                 'tools/accel_upper_coloured_v1/model.py','tools/accel_upper_am_v1/model.py','tools/accel_upper_forward_v1/kernel.py',
                 'tools/accel_upper_joint_v1/moments.py','tools/accel_upper_carrier_v1/spectral.py','tools/research_archive_v1.py',
                 'research/accel_upper_realization_v1_plan.json']:
        dest=a.out/'exact_sources'/name;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(repo/name,dest);r['sources'][name]=sha(repo/name)
    r['known'],arrays=known();np.savez_compressed(a.out/'known.npz',**arrays);r['known_sha256']=sha(a.out/'known.npz');save(a.out/'report.json',r)
    print(dict(known=r['known']),flush=True)
    parent=a.workspace/'baselines/accel_upper_coloured_v1';r['parent_manifest_sha256']=sha(parent/'manifest.json');table={v['path']:v['sha256'] for v in load(parent/'manifest.json')['files']}
    def read(name):
        path=parent/name;assert sha(path)==table[name];r['parent_files'][name]=table[name];return path
    fit=load(read('evidence/fit1/report.json'));assert load(read('evidence/audit1/report.json'))['result']=='passed'
    for row in fit['observations']:
        model_name='evidence/fit1/'+row['file'];carrier_name='inputs/parent/'+row['carrier_parent_file']
        with np.load(read(model_name)) as f,np.load(read(carrier_name)) as carrier:
            h=f['impulse'];tile=f['tile'];L=f['L'];tau=float(f['parameters'][-1]);q=carrier['q'];warm=len(q)-1
            power=np.diag(carrier['covariance'][len(h)-1]);filtered_power=np.diag(f['refilter_gain_covariance'][len(f['refilter_gain_covariance'])//2])
            frames=BLOCKS*len(tile)*480;folder=a.out/(row['segment']+'_'+row['branch']);folder.mkdir()
            records=[]
            for carrier_seed,gain_seed in SEEDS:
                white,c=generate_carrier(h,frames+warm,carrier_seed);motion=generate(L,tau,frames+warm,gain_seed);full=c*motion['gain']
                filtered=np.column_stack([signal.oaconvolve(full[:,i],q[:,i])[:len(full)] for i in range(4)])[warm:];raw=full[warm:]
                paths={};stats={}
                for stage,values,P in [('raw',raw,power),('refilter',filtered,filtered_power)]:
                    path=folder/(str(gain_seed)+'_'+stage+'.npy');np.save(path,values);paths[stage]=dict(file=path.relative_to(a.out).as_posix(),sha256=sha(path))
                    observed=observe_run(values,tile,P,BLOCKS)
                    stats.update({stage+'_'+key:value for key,value in observed.items()})
                file=folder/(str(gain_seed)+'_observations.npz');np.savez_compressed(file,**stats)
                record=dict(carrier_seed=carrier_seed,gain_seed=gain_seed,frames=frames,warmup_frames=warm,files=paths,
                    observation_file=file.relative_to(a.out).as_posix(),observation_sha256=sha(file),raw_peak=float(abs(raw).max()),
                    refilter_peak=float(abs(filtered).max()),gain_squared_mean=np.mean(motion['gain'][warm:]**2,axis=0).tolist())
                records.append(record);r['records']+=1;r['blocks_observed']+=2*BLOCKS
                save(a.out/'report.json',r);print(dict(segment=row['segment'],branch=row['branch'],gain_seed=gain_seed,frames=frames),flush=True)
                del white,c,motion,full,filtered,raw,stats,values
            file=folder/'model_observation.npz'
            np.savez_compressed(file,tile=tile,theoretical_power=power,filtered_theoretical_power=filtered_power,energy_expected=f['prediction'],source_target=f['target'],
                Welch_raw_expected=f['Welch_gain'],Welch_refilter_expected=f['Welch_refilter_gain'],parameters=f['parameters'])
            r['observations'].append(dict(segment=row['segment'],branch=row['branch'],fit_available=row['fit']['available'],model_parent_file=model_name,
                carrier_parent_file=carrier_name,file=file.relative_to(a.out).as_posix(),sha256=sha(file),records=records,
                blocks_per_run=BLOCKS,frames_per_block=len(tile)*480,within_source_windows=len(tile)))
            save(a.out/'report.json',r)
    assert len(r['observations'])==12 and r['records']==36 and r['blocks_observed']==576
    r.update(result='all12_continuous_source_realizations_and576observations_complete',new_listening_audio=False,new_runtime_profile=False,
        original_model_parameters_unchanged=True,post_refilter_fourth_moment_not_predicted=True,independent_runs=3,within_run_blocks_not_independent=True)
except Exception as exc:r.update(result='failed',error=repr(exc));raise
finally:save(a.out/'report.json',r)
print(dict(result=r['result'],records=r['records'],blocks=r['blocks_observed']),flush=True)
