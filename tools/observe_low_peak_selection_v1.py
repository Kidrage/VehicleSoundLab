"""Training-only complete peak-stage trace for the rejected A source attempt."""
import argparse,collections,json,shutil,sys
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--workspace',type=Path,required=True)
p.add_argument('--out',type=Path,required=True);a=p.parse_args();repo=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(a.workspace/'tools/python_deps'))
import numpy as np
import soundfile as sf
from drive_evidence_v1.sources import sha
from low_peak_selection_v1 import trace,controls

def load(p):return json.loads(p.read_text(encoding='utf-8'))
def save(p,obj):p.write_text(json.dumps(obj,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8',newline='\n')

a.out.mkdir(parents=True,exist_ok=False);r=dict(result='running',sources={})
try:
    plan=load(repo/'research/idle_modal_v1_plan.json')
    for path in [Path(__file__),repo/'research/low_peak_selection_v1_plan.json',repo/'research/idle_modal_v1_plan.json',
        repo/'tools/idle_modal_v1/modal.py',repo/'tools/drive_evidence_v1/sources.py',
        *sorted((repo/'tools/low_peak_selection_v1').glob('*.py'))]:
        dest=a.out/'exact_sources'/path.relative_to(repo);dest.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(path,dest);r['sources'][path.relative_to(repo).as_posix()]=sha(path)
    r['controls'],fixtures=controls.run(plan)
    np.savez_compressed(a.out/'known_signals.npz',**fixtures)
    save(a.out/'controls.json',r['controls']);print(json.dumps(dict(stage='known_controls',controls=r['controls'])),flush=True)
    parent=a.workspace/'references/analysis/fixed_source_profiles_v1/trial1/A_exterior_low_rev'
    x,rate=sf.read(parent/'training.wav',always_2d=True)
    # Compare exact training input to immutable previous freeze, no new source cut.
    assert sha(parent/'training.wav')==sha(a.workspace/'baselines/fixed_source_profiles_v1/evidence/trial1/A_exterior_low_rev/training.wav')
    evidence=load(parent/'fit_evidence.json')['modal'];anchors=[f for f in evidence['anchor_frequencies_hz'] if f<120]
    n,hop=plan['analysis_frames'],plan['analysis_hop'];windows=[]
    for j,start in enumerate(range(0,len(x)-n+1,hop)):
        result=trace.window(x[start:start+n],rate,plan)
        result.update(index=j,source_center_seconds=208+(start+(n-1)/2)/rate,
            anchors=[trace.anchor(result,f,plan['tracking_radius_hz']) for f in anchors])
        windows.append(result)
    summary=[]
    for k,f in enumerate(anchors):
        rows=[w['anchors'][k] for w in windows];reasons=collections.Counter()
        for row in rows:
            if row['status']=='absent':
                if row['absence_reason']=='no_raw_maximum_in_anchor_radius':reasons['no_raw_maximum_in_anchor_radius']+=1
                else:
                    for raw in row['raw_candidates']:reasons[raw['first_rejection']]+=1
        supported=sum(row['status']=='supported' for row in rows)/len(rows)
        old_index=evidence['anchor_frequencies_hz'].index(f)
        assert supported==evidence['support_fraction'][old_index]
        summary.append(dict(anchor_hz=f,support_fraction=supported,absence_stage_counts=dict(reasons),
            strongest_low_native_bins_hz=[w['strongest_low_native_bin_hz'] for w in windows]))
    save(a.out/'windows.json',windows)
    r.update(result='all7_training_windows_and8_low_anchor_selection_paths_traced',
        training_sha256=sha(parent/'training.wav'),old_evidence_sha256=sha(parent/'fit_evidence.json'),
        anchors=summary,windows=len(windows),window_trace_sha256=sha(a.out/'windows.json'),
        holdout_used=False,runtime_changed=False,selector_changed=False,
        limits=['Overlapping windows are not independent trials.',
            'Nearest peaks and failed fixed-anchor support do not prove line identity or physical FM.',
            'Known chirp establishes a counterexample to treating fixed-frequency support as generic source presence; no new real trajectory or audio profile.'])
except Exception as exc:r.update(result='failed',error=repr(exc));raise
finally:save(a.out/'report.json',r)
print(json.dumps(dict(result=r['result'],anchors=r.get('anchors')),ensure_ascii=False))
