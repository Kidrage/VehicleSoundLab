"""Check known mixtures then observe all frozen F3 tiles with unchanged scale guides."""
import argparse,json,shutil,sys
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--workspace',type=Path,required=True)
p.add_argument('--out',type=Path,required=True);a=p.parse_args();repo=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(a.workspace/'tools/python_deps'))
import numpy as np
from research_archive_v1 import load,save,sha
from drive_evidence_v1.sources import read
from accel_ridges_v1.observe import inventory,correspondence
from accel_ridges_v1.checks import controls
a.out.mkdir(parents=True,exist_ok=False);r=dict(result='running',sources={},observations=[],synthesis_profile_exported=False)
try:
    plan_path=repo/'research/accel_ridges_v1_plan.json';plan=load(plan_path)
    for path in [Path(__file__),plan_path,repo/'tools/research_archive_v1.py',repo/'tools/drive_evidence_v1/sources.py',
                 *sorted((repo/'tools/accel_ridges_v1').glob('*.py'))]:
        name=path.relative_to(repo);dest=a.out/'exact_sources'/name;dest.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(path,dest);r['sources'][name.as_posix()]=sha(path)
    checks,fixtures=controls(plan);save(a.out/'controls.json',checks);np.savez_compressed(a.out/'known.npz',**fixtures)
    r['controls']={name:row['evidence']['counts'] for name,row in checks.items() if 'evidence' in row}
    save(a.out/'report.json',r);print(dict(stage='known_controls',results=r['controls']),flush=True)
    prior_path=a.workspace/'references/analysis/accel_material_v1/observe1/report.json';prior=load(prior_path)
    r['parent_report_sha256']=sha(prior_path)
    for name in plan['segments']:
        original=next(row for row in prior['observations'] if row['segment']==name)
        audio,provenance=read(a.workspace,name,'fixed_window_spectral_observation')
        assert provenance==original['provenance'] and len(audio)%plan['tile_frames']==0
        frozen=np.load(prior_path.parent/original['arrays']);assert np.array_equal(audio,frozen['audio'])
        inventories=[inventory(audio[i:i+plan['tile_frames']],plan) for i in range(0,len(audio),plan['tile_frames'])]
        guides=[{key:tile['spectral_scale'][key] for key in ['ratio','supported']} for tile in original['tiles']]
        evidence=correspondence(inventories,guides,plan)
        save(a.out/(name+'.json'),dict(provenance=provenance,inventories=inventories,guides=guides,evidence=evidence))
        np.savez_compressed(a.out/(name+'.npz'),audio=audio)
        r['observations'].append(dict(segment=name,tiles=len(inventories),reference_peaks=len(evidence['classes']),counts=evidence['counts']))
        print(r['observations'][-1],flush=True)
    r.update(result='native_guided_ridge_observations_complete',phase_or_RPM_measured=False,
        source_identity_established=False,runtime_changed=False,plan=plan)
except Exception as exc:r.update(result='failed',error=repr(exc));raise
finally:save(a.out/'report.json',r)
