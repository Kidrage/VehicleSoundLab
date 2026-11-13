"""Fit ONE declared two-coordinate idle model; preserve all failures and exact bytes."""
import argparse
import shutil
import sys
from pathlib import Path
p = argparse.ArgumentParser(description=__doc__)
for name in ['workspace','out']: p.add_argument('--'+name,type=Path,required=True)
a = p.parse_args(); repo = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(a.workspace/'tools/python_deps'))
import numpy as np
from research_archive_v1 import load, save, sha
from idle_phase_recipe_v1.phase import fit, known

a.out.mkdir(parents=True,exist_ok=False)
r = dict(result='running',sources={},inputs={})
try:
    for name in ['tools/fit_idle_phase_recipe_v1.py','tools/idle_phase_recipe_v1/phase.py',
                 'tools/research_archive_v1.py','research/idle_phase_recipe_v1_plan.json']:
        path = repo/name; dest=a.out/'exact_sources'/name;dest.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(path,dest);r['sources'][name]=sha(path)
    r['known']=known()
    source = a.workspace/'baselines/idle_closure_evidence_v1/evidence/observe1'
    report = load(source/'report.json'); table={v['label']:v for v in report['observations']}
    arrays={}
    for part in ['train','check']:
        row=table['source_'+part];path=source/row['file']; assert sha(path)==row['sha256']
        r['inputs'][str(path)]=sha(path)
        with np.load(path) as data: arrays[part]=data['phasors']
    model=fit(arrays['train']);save(a.out/'model.json',model)
    r.update(result='source_VAR2_stable_pending_waveform_and_listening',model_sha256=sha(a.out/'model.json'),
        model=model,fit_used_check=False,runtime_changed=False)
except Exception as exc:r.update(result='failed',error=repr(exc));raise
finally:save(a.out/'report.json',r)
print(dict(result=r['result'],spectral_radius=r.get('model',{}).get('spectral_radius'),
           carrier_hz=r.get('model',{}).get('carrier_hz')),flush=True)
