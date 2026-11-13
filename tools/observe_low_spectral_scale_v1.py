"""Check cross-band spectral scaling of all original A training windows."""
import argparse,json,shutil,sys
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--workspace',type=Path,required=True)
p.add_argument('--out',type=Path,required=True);a=p.parse_args();repo=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(a.workspace/'tools/python_deps'))
import numpy as np
import soundfile as sf
from drive_evidence_v1.sources import sha
from low_peak_selection_v1 import scale

def load(p):return json.loads(p.read_text(encoding='utf-8'))
def save(p,obj):p.write_text(json.dumps(obj,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8',newline='\n')

a.out.mkdir(parents=True,exist_ok=False);r=dict(result='running',sources={},source_read=False)
try:
    plan=load(repo/'research/low_spectral_scale_v1_plan.json')
    for path in [Path(__file__),repo/'research/low_spectral_scale_v1_plan.json',
        repo/'tools/low_peak_selection_v1/scale.py',repo/'tools/accel_material_v1/features.py',
        repo/'tools/idle_material_v1/features.py',repo/'tools/drive_evidence_v1/sources.py']:
        dest=a.out/'exact_sources'/path.relative_to(repo);dest.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(path,dest);r['sources'][path.relative_to(repo).as_posix()]=sha(path)
    r['controls']=scale.controls(plan);save(a.out/'controls.json',r['controls'])
    print(json.dumps(dict(stage='dense_controls_passed',known=r['controls']['dense_known_scales'])),flush=True)
    path=a.workspace/plan['input'];frozen=a.workspace/'baselines/fixed_source_profiles_v1/evidence/trial1/A_exterior_low_rev/training.wav'
    assert sha(path)==sha(frozen);audio,rate=sf.read(path,always_2d=True);assert rate==48000
    r['source_read']=True;n,hop=plan['native_frames'],plan['hop_frames']
    features=[];cells=[]
    for start in range(0,len(audio)-n+1,hop):
        f,observed=scale.feature(audio[start:start+n],plan);features.append(f);cells.append(observed['cells'])
    reference=features[plan['reference_window']];rows=[]
    for i,current in enumerate(features):
        match=scale.compare(reference,current,plan)
        rows.append(dict(window=i,source_center_seconds=208+(i*hop+(n-1)/2)/48000,**match))
        print(json.dumps(dict(stage='window',index=i,ratio=match['global_match']['ratio'],
            supported=match['supported'],band_shifts=[x['shift_bins'] for x in match['band_matches']])),flush=True)
    np.savez_compressed(a.out/'observations.npz',features=np.asarray(features),cells=np.asarray(cells),frequency=observed['frequency'])
    save(a.out/'windows.json',rows)
    r.update(result='all7_training_cross_band_spectral_scales_observed',
        input_sha256=sha(path),supported_windows=sum(row['supported'] for row in rows),
        windows=[dict(index=row['window'],ratio=row['global_match']['ratio'],
            global_supported=row['global_match']['supported'],supported=row['supported'],
            band_shift_spread_bins=row['band_shift_spread_bins']) for row in rows],
        holdout_used=False,profile_generated=False,phase_or_RPM=False,runtime_changed=False,
        next='Only use qualified scale observations to investigate line correspondence; unsupported windows remain explicit gaps, not a synthesized trajectory.')
except Exception as exc:r.update(result='failed',error=repr(exc));raise
finally:save(a.out/'report.json',r)
