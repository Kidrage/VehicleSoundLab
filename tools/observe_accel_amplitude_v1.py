"""All declared cross-passage amplitude transfers; no source audio fitting."""
import argparse,itertools,shutil,sys
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__)
for key in ['workspace','out']:p.add_argument('--'+key,type=Path,required=True)
a=p.parse_args();repo=Path(__file__).resolve().parents[1];sys.path.insert(0,str(a.workspace/'tools/python_deps'))
import numpy as np
from research_archive_v1 import load,save,sha
from accel_amplitude_v1.model import compile_model,predict,train_rows
from accel_amplitude_v1.checks import controls
from accel_material_v1.features import whiten,scale_match
from idle_material_v1.features import spectrum
from accel_ridges_v1.observe import associate
a.out.mkdir(parents=True,exist_ok=False);r=dict(result='running',sources={},pairs=[])
try:
    plan_path=repo/'research/accel_amplitude_v1_plan.json';plan=load(plan_path)
    scale_plan=load(repo/'research/accel_material_v1_plan.json');ridge_plan=load(repo/'research/accel_ridges_v1_plan.json')
    sources=[Path(__file__),plan_path,repo/'research/accel_material_v1_plan.json',repo/'research/accel_ridges_v1_plan.json',
        repo/'tools/research_archive_v1.py',repo/'tools/accel_material_v1/features.py',repo/'tools/accel_material_v1/checks.py',
        repo/'tools/idle_material_v1/features.py',repo/'tools/accel_ridges_v1/observe.py',*sorted((repo/'tools/accel_amplitude_v1').glob('*.py'))]
    for path in sources:
        name=path.relative_to(repo);dest=a.out/'exact_sources'/name;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(path,dest);r['sources'][name.as_posix()]=sha(path)
    save(a.out/'known_controls.json',controls(scale_plan,ridge_plan))
    parent=a.workspace/'baselines/accel_chirp_v1/evidence/observe1';ridge=a.workspace/'baselines/accel_ridges_v1/evidence/observe2'
    rows={};reference={};features={};models={};inputs={}
    for name in plan['segments']:
        path=parent/name/'fits.json';rows[name]=load(path);inputs[str(path)]=sha(path)
        src=load(ridge/(name+'.json'));reference[name]=src['evidence']['reference_hz']
        audio=np.load(ridge/(name+'.npz'))['audio'];first=audio[:12000]
        power=spectrum(first,scale_plan['bands_hz']);features[name]=whiten(power['cells'],power['frequency'],scale_plan['spectral_scale'])
        np.savez_compressed(a.out/(name+'_first.npz'),audio=first,cells=power['cells'],frequency=power['frequency'],feature=features[name])
        models[name]=[]
        for k in range(len(reference[name])):
            train=train_rows(rows[name],k)
            model=compile_model([np.log(ratio) for _,ratio,_ in train],[line['amplitude_LR'] for _,_,line in train],
                [line['frequency_hz'] for _,_,line in train],np.array([ratio for _,ratio,_ in train]),np.log(1.03)) if train else None
            models[name].append(dict(reference_index=k,training_tiles=[i for i,_,_ in train],model=model))
        save(a.out/(name+'_models.json'),models[name])
    for source,target in itertools.permutations(plan['segments'],2):
        match=scale_match(features[source],features[target],scale_plan['spectral_scale'])
        graph=associate(reference[source],reference[target],match['ratio'],4.,ridge_plan)
        pair=dict(source=source,target=target,scale_match=match,association=graph,references=[],window_shape=[])
        for k,state in enumerate(graph['state']):
            row=dict(source_reference=k,association=state,target_reference=graph['chosen'][k],rows=[],status='uncompared')
            model=models[source][k]['model'];row['model_available']=model is not None
            if not match['supported']:row['status']='scale_unsupported'
            elif state!='unique':row['status']='association_'+state
            elif model is None:row['status']='insufficient_training'
            else:
                fitted=train_rows(rows[target],graph['chosen'][k]);inside=[]
                for tile,ratio,line in fitted:
                    x=float(np.log(match['ratio']*ratio));within=model['coordinate_min']<=x<=model['coordinate_max']
                    check=dict(tile=tile,coordinate=x,within_source_range=within)
                    if within:
                        predicted=predict(model,x);observed=np.array(line['amplitude_LR'])
                        check.update(predicted_amplitude_LR={key:value.tolist() for key,value in predicted.items()},
                            observed_amplitude_LR=observed.tolist(),frequency_error_hz=float(line['frequency_hz']-model['frequency_at_ratio1_hz']*np.exp(x)),
                            error_db_LR={key:(20*np.log10(observed/value)).tolist() for key,value in predicted.items()})
                        inside.append(check)
                    row['rows'].append(check)
                row['eligible_target_count']=len(fitted);row['within_count']=len(inside)
                if len(inside)<3 or len(inside)<.5*len(fitted):row['status']='insufficient_target_range'
                else:
                    row['status']='compared';row['median_absolute_error_db']={key:float(np.median(abs(np.array([v['error_db_LR'][key] for v in inside])))) for key in ['RMS','geometric','log_linear']}
                    row['maximum_frequency_error_hz']=max(abs(v['frequency_error_hz']) for v in inside)
                    row['diagnostic_targets_met']={key:bool(value<=3 and row['maximum_frequency_error_hz']<=4) for key,value in row['median_absolute_error_db'].items()}
            pair['references'].append(row)
        for tile in range(len(rows[target])):
            used=[(row['source_reference'],check) for row in pair['references'] if row['status']=='compared' for check in row['rows'] if check['tile']==tile and check['within_source_range']]
            if len(used)<3:continue
            errors={key:np.array([check['error_db_LR'][key] for _,check in used]) for key in ['RMS','geometric','log_linear']}
            pair['window_shape'].append(dict(tile=tile,source_references=[k for k,_ in used],
                common_error_db_LR={key:value.mean(axis=0).tolist() for key,value in errors.items()},
                centered_error_db_LR={key:(value-value.mean(axis=0)).tolist() for key,value in errors.items()},
                warning='Observed-error decomposition only; never used to change predictions or monitoring gains'))
        used=[row for row in pair['references'] if row['status']=='compared']
        pair['summary']=dict(scale_supported=match['supported'],unique_associations=graph['state'].count('unique'),
            compared=len(used),status_counts={status:sum(row['status']==status for row in pair['references']) for status in sorted({row['status'] for row in pair['references']})},
            median_reference_error_db={key:float(np.median([row['median_absolute_error_db'][key] for row in used])) if used else None for key in ['RMS','geometric','log_linear']},
            amplitude3dB_pass={key:sum(row['median_absolute_error_db'][key]<=3 for row in used) for key in ['RMS','geometric','log_linear']},
            both_diagnostics_pass={key:sum(row['diagnostic_targets_met'][key] for row in used) for key in ['RMS','geometric','log_linear']},
            log_linear_better_than_geometric=sum(row['median_absolute_error_db']['log_linear']<row['median_absolute_error_db']['geometric'] for row in used))
        save(a.out/(source+'_to_'+target+'.json'),pair);r['pairs'].append(dict(source=source,target=target,**pair['summary']))
        print(r['pairs'][-1],flush=True)
    r.update(result='all6_cross_passage_amplitude_checks_complete',plan=plan,parent_fits_sha256=inputs,
        runtime_changed=False,profile_exported=False,pristine_holdout=False,physical_load_or_RPM_identified=False,
        target_amplitude_used_for_training=False,source_only_models=True)
except Exception as exc:r.update(result='failed',error=repr(exc));raise
finally:save(a.out/'report.json',r)
