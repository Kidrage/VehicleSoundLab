"""All48 frozen F3 upper-band observations after declared known controls."""
import argparse,shutil,sys
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__)
for key in ['workspace','out']:p.add_argument('--'+key,type=Path,required=True)
a=p.parse_args();repo=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(a.workspace/'tools/python_deps'))
import numpy as np
from research_archive_v1 import load,save,sha
from accel_upper_inventory_v1.observe import measure
from accel_upper_inventory_v1.checks import fixtures,check
from accel_ridges_v1.observe import inventory

a.out.mkdir(parents=True,exist_ok=False);r=dict(result='running',sources={},known={},observations=[],parent_files={})
try:
    plan_path=repo/'research/accel_upper_inventory_v1_plan.json';plan=load(plan_path)
    names=[Path(__file__),plan_path,repo/'tools/research_archive_v1.py',repo/'tools/accel_ridges_v1/observe.py',
           repo/'research/accel_ridges_v1_plan.json',
           *sorted((repo/'tools/accel_upper_inventory_v1').glob('*.py'))]
    for path in names:
        name=path.relative_to(repo);dest=a.out/'exact_sources'/name;dest.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(path,dest);r['sources'][name.as_posix()]=sha(path)
    known=a.out/'known';known.mkdir()
    for name,audio in fixtures(plan).items():
        row,z=measure(audio,plan);save(known/(name+'.json'),row);np.savez_compressed(known/(name+'.npz'),**z)
        r['known'][name]=row
    r['controls']=check(r['known']);save(a.out/'known_report.json',r['controls'])
    print(dict(stage='known_controls',**r['controls']),flush=True)
    parent=a.workspace/'baselines/accel_candidate_prediction_v1';manifest=load(parent/'manifest.json')
    table={v['path']:v['sha256'] for v in manifest['files']}
    r['parent_manifest_sha256']=sha(parent/'manifest.json')
    def read_parent(name):
        path=parent/name;digest=sha(path);assert table[name]==digest
        r['parent_files'][name]=digest;return path
    validation=load(read_parent('validation.json'))
    assert validation['result']=='all48_F3_observations_audited_NO_source_identity_or_audio_promotion'
    assert validation['audit']['windows']==48
    old_plan=load(repo/'research/accel_ridges_v1_plan.json')
    for case in ['F3_fifth1','F3_fifth2','F3_sixth']:
        folder=a.out/case;folder.mkdir()
        originals=load(read_parent(f'evidence/observe1/{case}/initialization.json'))
        rows=[]
        for i,original in enumerate(originals['inventories']):
            audio=np.load(read_parent(f'evidence/observe1/{case}/native_{i:02d}.npz'))['audio']
            row,z=measure(audio,plan)
            old=inventory(audio,old_plan)
            assert old['bin']==[v for v in original['bin'] if v>=50]
            assert [v['bin'] for v in row['peaks'] if v['old_accepted']]==[v for v in old['bin'] if v>=1000]
            row.update(window=i,old_inventory=old)
            save(folder/f'tile_{i:02d}.json',row);np.savez_compressed(folder/f'tile_{i:02d}.npz',**z)
            rows.append(row)
        summary=dict(segment=case,windows=len(rows),bands=[])
        for b,band in enumerate(plan['upper_bands_hz']):
            keys=rows[0]['bands'][b]['counts']
            summary['bands'].append(dict(band_hz=band,counts={key:sum(row['bands'][b]['counts'][key] for row in rows) for key in keys},
                maximum_relative_to_old_db_range=[min(row['bands'][b]['maximum_relative_to_old_db'] for row in rows),max(row['bands'][b]['maximum_relative_to_old_db'] for row in rows)]))
        r['observations'].append(summary);save(a.out/'report.json',r);print(summary,flush=True)
    r.update(result='all48_upper_inventory_rejection_census_complete',plan=plan,new_audio_or_profile=False,
             source_identity_or_RPM_load_qualified=False,runtime_changed=False)
except Exception as exc:r.update(result='failed',error=repr(exc));raise
finally:save(a.out/'report.json',r)
