"""Correct omitted strongest original reference peaks, fit all48 native windows."""
import argparse,shutil,sys,time
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__)
for key in ['workspace','out']:p.add_argument('--'+key,type=Path,required=True)
a=p.parse_args();repo=Path(__file__).resolve().parents[1];sys.path.insert(0,str(a.workspace/'tools/python_deps'))
import numpy as np
from research_archive_v1 import load,save,sha
from accel_chirp_v1.fit import fit
from accel_chirp_v1.checks import controls
from accel_ridges_v1.observe import inventory,associate
from accel_wideband_v1.coverage import oscillator_model,decomposition
a.out.mkdir(parents=True,exist_ok=False);r=dict(result='running',sources={},observations=[])
try:
    plan_path=repo/'research/accel_full_inventory_v1_plan.json';plan=load(plan_path)
    fit_plan=load(repo/'research/accel_chirp_v1_plan.json');ridge_plan=load(repo/'research/accel_ridges_v1_plan.json')
    coverage_plan=load(repo/'research/accel_coverage_v1_plan.json')
    sources=[Path(__file__),plan_path,repo/'research/accel_chirp_v1_plan.json',repo/'research/accel_ridges_v1_plan.json',
        repo/'research/accel_coverage_v1_plan.json',repo/'tools/accel_chirp_v1/fit.py',repo/'tools/accel_chirp_v1/checks.py',
        repo/'tools/line_motion_v1/local_chirps.py',repo/'tools/accel_ridges_v1/observe.py',
        repo/'tools/accel_wideband_v1/coverage.py',repo/'tools/research_archive_v1.py']
    for path in sources:
        name=path.relative_to(repo);dest=a.out/'exact_sources'/name;dest.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(path,dest);r['sources'][name.as_posix()]=sha(path)
    # Original full known chirp controls remain unchanged.
    check,fixtures=controls(fit_plan);(a.out/'known').mkdir()
    for name,values in fixtures.items():np.savez_compressed(a.out/'known'/(name+'.npz'),**values)
    n=12000;t=(np.arange(n)-n/2)/48000;freq=np.array([217.3,245.1,299.8,419.7,899.1,1499.])
    amp=np.array([.012,.01,.3,.04,.025,.01]);alpha=.05;phase=np.array([.3,-.8,.2,1.1,.5,-1.1])
    signal=np.sum(amp*np.cos(2*np.pi*(t[:,None]+.5*alpha*t[:,None]**2)*freq+phase),axis=1)
    audio=np.column_stack((signal,.7*signal));inv=inventory(audio,ridge_plan)
    assert len(inv['hz'])==6 and any(abs(f-299.8)<2 for f in inv['hz'])
    assert not any(abs(f-299.8)<2 for f in inv['hz'] if f>=300)
    nominal=np.array(inv['bin'])*4.;known,arrays=fit(audio,nominal,alpha*nominal,fit_plan)
    assert known['success'] and all(line['eligible'] for line in known['lines'])
    assert max(abs(line['frequency_hz']-truth) for line,truth in zip(known['lines'],freq))<.01
    assert max(abs(line['amplitude_LR'][0]-truth) for line,truth in zip(known['lines'],amp))<1e-5
    save(a.out/'controls.json',dict(original_controls=check,omitted_dominant=known,inventory=inv,truth_frequency_hz=freq.tolist(),
        truth_amplitude_LR=(amp[:,None]*np.array([[1.,.7]])).tolist(),old_cutoff_omits_strongest=True))
    np.savez_compressed(a.out/'known/omitted_dominant.npz',audio=audio,**arrays)
    print(dict(stage='known_controls',old_cutoff_omits_strongest=True),flush=True)
    parent=a.workspace/'baselines/accel_ridges_v1/evidence/observe2'
    for name in plan['segments']:
        source=load(parent/(name+'.json'));audio=np.load(parent/(name+'.npz'))['audio'];refs=source['inventories'][0]['hz']
        old=load(a.workspace/'baselines/accel_chirp_v1/evidence/observe1'/name/'fits.json')
        guides=source['guides'];graphs=[associate(refs,inv['hz'],g['ratio'],4.,ridge_plan) for inv,g in zip(source['inventories'],guides)]
        folder=a.out/name;folder.mkdir();rows=[]
        save(folder/'correspondence.json',dict(reference_hz=refs,graphs=graphs,guides=guides,
            parent_json_sha256=sha(parent/(name+'.json')),parent_audio_sha256=sha(parent/(name+'.npz'))))
        for i,graph in enumerate(graphs):
            selected=[k for k,state in enumerate(graph['state']) if state=='unique']
            order=sorted(selected,key=lambda k:source['inventories'][i]['bin'][graph['chosen'][k]])
            nominal=[];initial=[]
            def frequency(v,k):return source['inventories'][v]['hz'][graphs[v]['chosen'][k]]
            for k in order:
                nominal.append(source['inventories'][i]['bin'][graph['chosen'][k]]*4.)
                near=[v for v in [i-1,i+1] if 0<=v<len(graphs) and graphs[v]['state'][k]=='unique']
                if len(near)==2:initial.append((frequency(i+1,k)-frequency(i-1,k))/.5)
                elif near:initial.append((frequency(near[0],k)-frequency(i,k))/((near[0]-i)*.25))
                else:initial.append(0.)
            begin=time.perf_counter();tile=audio[i*n:(i+1)*n];result,arrays=fit(tile,nominal,initial,fit_plan)
            for k,line in zip(order,result['lines']):line['reference_index']=k
            result.update(tile=i,ratio=guides[i]['ratio'],guide_supported=guides[i]['supported'],seconds=time.perf_counter()-begin)
            result['coverage']={}
            for eligible,field in [(False,'all'),(True,'eligible')]:
                parts,error=decomposition(tile,oscillator_model(result,eligible=eligible),coverage_plan['bands_hz'])
                result['coverage'][field]=parts;assert error<1e-12
            result['old_fit_success']=old[i]['success'];result['old_eligible_count']=sum(v['eligible'] for v in old[i]['lines'])
            rows.append(result);save(folder/'fits.json',rows);np.savez_compressed(folder/f'tile_{i:02d}.npz',audio=tile,**arrays)
            print(dict(segment=name,tile=i,success=result['success'],lines=len(result['lines']),
                eligible=sum(v['eligible'] for v in result['lines']),seconds=result['seconds']),flush=True)
        r['observations'].append(dict(segment=name,tiles=len(rows),references=len(refs),successful=sum(row['success'] for row in rows),
            eligible_lines=sum(line['eligible'] for row in rows for line in row['lines'])))
        save(a.out/'report.json',r)
    r.update(result='full_original_reference_native_fits_complete',plan=plan,source_chirplet_run=False,
        physical_source_or_RPM_load=False,common_phase_qualified=False,audio_or_profile_exported=False,runtime_changed=False)
except Exception as exc:r.update(result='failed',error=repr(exc));raise
finally:save(a.out/'report.json',r)
