"""Native source/model coverage with interference, independent of failed dechirp gate."""
import argparse,shutil,sys
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__)
for key in ['workspace','out']:p.add_argument('--'+key,type=Path,required=True)
a=p.parse_args();repo=Path(__file__).resolve().parents[1];sys.path.insert(0,str(a.workspace/'tools/python_deps'))
import numpy as np
from research_archive_v1 import load,save,sha
from accel_wideband_v1.coverage import oscillator_model,decomposition
a.out.mkdir(parents=True,exist_ok=False);r=dict(result='running',sources={},observations=[],power_identity_max_error=0.)
try:
    plan_path=repo/'research/accel_coverage_v1_plan.json';plan=load(plan_path)
    for path in [Path(__file__),plan_path,repo/'tools/accel_wideband_v1/coverage.py',repo/'tools/research_archive_v1.py']:
        name=path.relative_to(repo);dest=a.out/'exact_sources'/name;dest.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(path,dest);r['sources'][name.as_posix()]=sha(path)
    n=12000;t=np.arange(n)/48000;bands=plan['bands_hz']
    amplitudes=np.array([.3,.2,.15,.1,.07,.04,.02]);freq=[80,220,600,1600,3000,6000,10000]
    known=sum(a*np.cos(2*np.pi*f*t) for a,f in zip(amplitudes,freq));known=np.column_stack((known,.7*known))
    exact,error=decomposition(known,known,bands);truth=amplitudes[:,None]**2/2*np.array([[1.,.49]])
    assert abs(np.array(exact['source'])-truth).max()<1e-12 and np.count_nonzero(exact['residual'])==0
    absent=known-amplitudes[-1]*np.cos(2*np.pi*freq[-1]*t)[:,None]*np.array([[1.,.7]])
    missing,error=decomposition(known,absent,bands)
    assert abs(np.array(missing['residual'])[-1]-truth[-1]).max()<1e-12
    destructive,error=decomposition(known,known*1.5,bands)
    assert np.all(np.array(destructive['model'])>np.array(destructive['source'])) and np.all(np.array(destructive['interference'])<0)
    assert error<1e-12
    save(a.out/'controls.json',dict(exact=exact,missing=missing,destructive=destructive,power_identity_error=error))
    parent=a.workspace/'baselines/accel_chirp_v1/evidence/observe1'
    for name in plan['segments']:
        rows=load(parent/name/'fits.json');folder=a.out/name;folder.mkdir();result=[]
        for i,row in enumerate(rows):
            path=parent/name/f'tile_{i:02d}.npz';saved=np.load(path);audio=saved['audio']
            all_model=oscillator_model(row);eligible_model=oscillator_model(row,eligible=True)
            assert abs(all_model-saved['reconstructed']).max()<1e-12
            all_parts,ae=decomposition(audio,all_model,bands);eligible_parts,ee=decomposition(audio,eligible_model,bands)
            r['power_identity_max_error']=max(r['power_identity_max_error'],ae,ee)
            frequencies=[line['frequency_hz'] for line in row['lines']]
            np.savez_compressed(folder/f'tile_{i:02d}.npz',audio=audio,all_model=all_model,eligible_model=eligible_model)
            result.append(dict(tile=i,parent_sha256=sha(path),fit_success=row['success'],guide_supported=row['guide_supported'],
                all_lines=len(row['lines']),eligible_lines=sum(line['eligible'] for line in row['lines']),
                frequency_min_hz=min(frequencies),frequency_max_hz=max(frequencies),all_parts=all_parts,eligible_parts=eligible_parts))
        summary=dict(segment=name,tiles=len(rows),rows=result,parent_fits_sha256=sha(parent/name/'fits.json'),aggregate={})
        for kind in ['all_parts','eligible_parts']:
            summed={key:np.sum([row[kind][key] for row in result],axis=0) for key in ['source','model','residual','interference']}
            total=summed['source'].sum(axis=0)
            summary['aggregate'][kind]=dict(powers={key:value.tolist() for key,value in summed.items()},
                source_fraction=(summed['source']/total).tolist(),model_over_source=(summed['model']/summed['source']).tolist(),
                residual_over_source=(summed['residual']/summed['source']).tolist(),cross_over_source=(summed['interference']/summed['source']).tolist())
        save(folder/'report.json',summary);r['observations'].append({key:summary[key] for key in ['segment','tiles','aggregate']})
        print(dict(segment=name,source_fraction_L=np.array(summary['aggregate']['all_parts']['source_fraction'])[:,0].tolist(),
            eligible_model_over_source_L=np.array(summary['aggregate']['eligible_parts']['model_over_source'])[:,0].tolist()),flush=True)
    r.update(result='all48_native_coverage_with_interference_observed',plan=plan,source_chirplet_run=False,
        physical_source_separation=False,runtime_changed=False,profile_or_audio_exported=False)
except Exception as exc:r.update(result='failed',error=repr(exc));raise
finally:save(a.out/'report.json',r)
