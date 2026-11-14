"""Check frozen F2 AM/relative-phase transfer before any joint synthesis proposal."""
import argparse,shutil,sys
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__)
for key in ['workspace','out']:p.add_argument('--'+key,type=Path,required=True)
a=p.parse_args();repo=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(a.workspace/'tools/python_deps'))
import numpy as np
from research_archive_v1 import load,save,sha
from idle_amp_phase_link_v1.observe import feature,target,fit,evaluate,covariance
from idle_amp_phase_link_v1.known import run

a.out.mkdir(parents=True,exist_ok=False)
r=dict(schema='vsl.idle-amp-phase-link/1',result='running',sources={},inputs={},cases=[],models={},evaluations=[])
def track(path):r['inputs'][str(path)]=sha(path);return path
try:
    for name in ['tools/observe_idle_amp_phase_link_v1.py','tools/idle_amp_phase_link_v1/observe.py',
        'tools/idle_amp_phase_link_v1/known.py','tools/research_archive_v1.py','research/idle_amp_phase_link_v1_plan.json']:
        dest=a.out/'exact_sources'/name;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(repo/name,dest)
        r['sources'][name]=sha(repo/name)
    r['known'],arrays=run();np.savez_compressed(a.out/'known.npz',**arrays)
    # Reuse actual, previously qualified FM/noAM and neighbor observations.
    old=a.workspace/'baselines/idle_phase_amplitude_v1/evidence/observe1'
    known=load(track(old/'report.json'));assert known['known']['result']=='known_AM_FM_observer_controls_passed'
    r['frozen_observer_controls']=[]
    with np.load(track(old/'known.npz')) as f:
        for label in ['constant','nonlinearFM','AM','combined','neighbor']:
            coefficients=f[label+'_coefficients'];z=f[('neighbor_phasors' if label=='neighbor' else label+'_phasors')]
            starts=np.arange(12000,122401,960);x=feature(z,starts);y=target(coefficients)
            std=np.std(y,axis=0)
            if label in ['constant','nonlinearFM']:assert std.max()<=.003
            file=a.out/('known_'+label+'.npz');np.savez_compressed(file,x=x,y=y,starts=starts)
            r['frozen_observer_controls'].append(dict(label=label,file=file.name,sha256=sha(file),observed_log_std=std.tolist(),
                scope='Frozen qualified acoustic observer, not physical AM separation; neighbor intentionally confounded'))
    parent=a.workspace/'baselines/idle_local_partition_v1/evidence/observe1'
    prior=load(track(parent/'report.json'));assert prior['result']=='local_selected_core_partition_observed'
    data={}
    for row in prior['cases']:
        if row['metadata']['kind'] not in ['source','samePSD_control']:continue
        file=track(parent/row['file']);assert sha(file)==row['sha256']
        with np.load(file) as f:x=feature(f['phasors'],f['starts']);y=target(f['local_coefficients']);starts=f['starts']
        assert x.shape==(116,4) and y.shape==(116,3)
        curves,count=covariance(np.column_stack((y,x)))
        dest=a.out/(row['label']+'.npz');np.savez_compressed(dest,x=x,y=y,starts=starts,covariance=curves,overlap_counts=count)
        r['cases'].append(dict(label=row['label'],metadata=row['metadata'],file=dest.name,sha256=sha(dest),
            input=str(file),input_sha256=sha(file),x_mean=x.mean(axis=0).tolist(),x_std=x.std(axis=0).tolist(),
            log_magnitude_mean=y.mean(axis=0).tolist(),log_magnitude_std=y.std(axis=0).tolist()))
        data[row['label']]=(x,y,curves)
    assert len(data)==8
    # All TRAIN fits are committed in memory/report before looking at any CHECK metric.
    families=['source','phase_149921','phase_277139','phase_381611']
    for family in families:
        x,y,_=data[family+'_train'];r['models'][family]=fit(x,y)
    save(a.out/'report.json',r)
    for family in families:
        model=r['models'][family]
        if not model['available']:continue
        for part in ['train','check']:
            label=family+'_'+part;x,y,_=data[label];result=evaluate(model,x,y)
            prediction=result.pop('prediction');dest=a.out/(label+'_prediction.npy');np.save(dest,prediction)
            r['evaluations'].append(dict(family=family,part=part,**result,prediction_file=dest.name,prediction_sha256=sha(dest)))
    source=r['models']['source'];r['source_model_to_phase_controls']=[]
    if source['available']:
        for label,(x,y,_) in data.items():
            if label.startswith('source'):continue
            result=evaluate(source,x,y);result.pop('prediction')
            r['source_model_to_phase_controls'].append(dict(label=label,**result))
    scale=np.std(np.column_stack(data['source_train'][:2][::-1]),axis=0)
    assert scale.shape==(7,) and np.all(scale>0)
    r['source_TRAIN_covariance_scale']=scale.tolist()
    r['all51lag_maximum_scaled_AM_phase_covariance']={label:float(abs(c[:,0:3,3:7]/scale[:3,None]/scale[None,3:]).max())
        for label,(_,_,c) in data.items()}
    r.update(result='frozen_AM_relative_phase_relationship_observed',source_portions=2,samePSD_portions=6,
        lag_seconds=(np.arange(-25,26)*.02).tolist(),CHECK_previously_inspected=True,
        source_trajectory_or_audio_generated=False,new_generator_exported=False,runtime_changed=False,listening_accepted=False)
except Exception as exc:r.update(result='failed',error=repr(exc));raise
finally:save(a.out/'report.json',r)
print(dict(result=r['result'],models={k:(v['available'],v.get('condition')) for k,v in r['models'].items()},
    check=[(v['family'],v['fractional_MSE_reduction']) for v in r['evaluations'] if v['part']=='check']),flush=True)
