"""Known controls then joint native fits of every existing F3 acceleration tile."""
import argparse,sys,shutil,time
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--workspace',type=Path,required=True)
p.add_argument('--out',type=Path,required=True);p.add_argument('--controls-only',action='store_true')
a=p.parse_args();repo=Path(__file__).resolve().parents[1];sys.path.insert(0,str(a.workspace/'tools/python_deps'))
import numpy as np
from research_archive_v1 import load,save,sha
from accel_chirp_v1.fit import fit
from accel_chirp_v1.checks import controls
a.out.mkdir(parents=True,exist_ok=False);r=dict(result='running',sources={},observations=[])
try:
    plan_path=repo/'research/accel_chirp_v1_plan.json';plan=load(plan_path)
    for path in [Path(__file__),plan_path,repo/'tools/research_archive_v1.py',repo/'tools/line_motion_v1/local_chirps.py',
                 *sorted((repo/'tools/accel_chirp_v1').glob('*.py'))]:
        name=path.relative_to(repo);dest=a.out/'exact_sources'/name;dest.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(path,dest);r['sources'][name.as_posix()]=sha(path)
    check,fixtures=controls(plan);save(a.out/'controls.json',check)
    folder=a.out/'known';folder.mkdir()
    for name,arrays in fixtures.items():np.savez_compressed(folder/(name+'.npz'),**arrays)
    print(dict(stage='known_controls',truth=check['analytic_truth']),flush=True)
    r['controls_complete']=True;save(a.out/'report.json',r)
    if a.controls_only:r['result']='known_controls_only';raise SystemExit
    parent=a.workspace/'references/analysis/accel_ridges_v1/observe2';r['parent_report_sha256']=sha(parent/'report.json')
    for name in plan['segments']:
        src=load(parent/(name+'.json'));audio=np.load(parent/(name+'.npz'))['audio'];e=src['evidence'];n=plan['frames']
        folder=a.out/name;folder.mkdir();rows=[]
        for i,row in enumerate(e['rows']):
            selected=[k for k,status in enumerate(row['moving']['state']) if status=='unique']
            order=sorted(selected,key=lambda k:src['inventories'][i]['bin'][row['moving']['chosen'][k]])
            nominal=[];initial=[]
            for k in order:
                j=row['moving']['chosen'][k];nominal.append(src['inventories'][i]['bin'][j]*4.)
                neighbours=[v for v in [i-1,i+1] if 0<=v<len(e['rows']) and e['rows'][v]['moving']['state'][k]=='unique']
                def frequency(v):return src['inventories'][v]['hz'][e['rows'][v]['moving']['chosen'][k]]
                if len(neighbours)==2:initial.append((frequency(i+1)-frequency(i-1))/.5)
                elif neighbours:initial.append((frequency(neighbours[0])-frequency(i))/((neighbours[0]-i)*.25))
                else:initial.append(0.)
            started=time.perf_counter();result,arrays=fit(audio[i*n:(i+1)*n],nominal,initial,plan)
            for k,line in zip(order,result['lines']):line['reference_index']=k
            result.update(tile=i,ratio=row['ratio'],guide_supported=row['guide_supported'],seconds=time.perf_counter()-started)
            rows.append(result);save(folder/'fits.json',rows);np.savez_compressed(folder/f'tile_{i:02d}.npz',audio=audio[i*n:(i+1)*n],**arrays)
            print(dict(segment=name,tile=i,count=len(nominal),success=result['success'],eligible=sum(x['eligible'] for x in result['lines']),seconds=result['seconds']),flush=True)
        half=len(rows)//2;predictions=[]
        for k,f0 in enumerate(e['reference_hz']):
            def fitted(indices):
                return [(i,line) for i in indices if rows[i]['guide_supported'] for line in rows[i]['lines'] if line['reference_index']==k and line['eligible']]
            train=fitted(range(half));check=fitted(range(half,len(rows)))
            if len(train)<3 or len(check)<3:
                predictions.append(dict(reference_index=k,training_count=len(train),check_count=len(check),status='insufficient'));continue
            frequency=float(np.median([line['frequency_hz']/rows[i]['ratio'] for i,line in train]))
            amplitude=np.sqrt(np.mean([np.array(line['amplitude_LR'])**2 for i,line in train],axis=0));observed=[]
            for i,line in check:
                error=line['frequency_hz']-frequency*rows[i]['ratio'];db=20*np.log10(np.maximum(line['amplitude_LR'],1e-300)/np.maximum(amplitude,1e-300))
                observed.append(dict(tile=i,frequency_error_hz=float(error),amplitude_error_db_LR=db.tolist()))
            max_frequency=max(abs(v['frequency_error_hz']) for v in observed)
            median_db=float(np.median(abs(np.array([v['amplitude_error_db_LR'] for v in observed]))))
            predictions.append(dict(reference_index=k,training_count=len(train),check_count=len(check),status='compared',
                training_frequency_hz=frequency,training_amplitude_LR=amplitude.tolist(),check=observed,
                maximum_frequency_error_hz=max_frequency,median_absolute_amplitude_error_db=median_db,
                diagnostic_target_met=bool(max_frequency<=4 and median_db<=3)))
        save(folder/'predictions.json',predictions)
        summary=dict(segment=name,tiles=len(rows),successful=sum(x['success'] for x in rows),local_lines=sum(len(x['lines']) for x in rows),
            locally_eligible=sum(line['eligible'] for x in rows for line in x['lines']),
            compared=sum(x['status']=='compared' for x in predictions),diagnostic_targets_met=sum(x.get('diagnostic_target_met',False) for x in predictions))
        r['observations'].append(summary);save(a.out/'report.json',r)
    r.update(result='native_chirp_fits_and_conditional_parameter_checks_complete',profile_exported=False,RPM_measured=False,
        physical_source_identified=False,phase_continuity_established=False,pristine_holdout=False,runtime_changed=False)
except SystemExit:raise
except Exception as exc:r.update(result='failed',error=repr(exc));raise
finally:save(a.out/'report.json',r)
