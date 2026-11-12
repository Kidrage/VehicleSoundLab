"""Scoped stationary train/heldout evidence and optional existing-C candidate."""
import argparse
import json
from pathlib import Path
import shutil
import sys

p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--workspace',type=Path,required=True)
p.add_argument('--validated',type=Path,required=True)
p.add_argument('--qualified',type=Path,required=True)
p.add_argument('--case-plan',type=Path)
p.add_argument('--probe',type=Path,required=True)
p.add_argument('--out',type=Path,required=True)
a=p.parse_args();repo=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(a.workspace/'tools/python_deps'))
import numpy as np
import soundfile as sf
from drive_evidence_v1.sources import sha
from stationary_dna_v1.source import inspect
from stationary_dna_v1.fit import fit,normalized_playback,physical_playback
from stationary_dna_v1.measure import moments,difference

a.out.mkdir(parents=True,exist_ok=False)
r=dict(schema='vsl.B-stationary-dna-fit/1',result='running',cases={},sources={},runtime_modified=False)
try:
    plan_path=repo/'research/B_stationary_dna_v1_validation_plan.json'
    plan=json.loads(plan_path.read_text(encoding='utf-8'))
    validated=json.loads((a.validated/'report.json').read_text(encoding='utf-8'))
    assert validated['result']=='passed','Independent fixture validation failed; do not fit'
    assert validated['plan_sha256']==sha(plan_path)
    for name,digest in validated['sources'].items():
        assert sha(repo/name)==digest and sha(a.validated/'exact_sources'/name)==digest
    case_plan_path=a.case_plan.resolve() if a.case_plan else repo/plan['input_plan']
    case_plan=json.loads(case_plan_path.read_text(encoding='utf-8'))
    sources=[Path(__file__),plan_path,case_plan_path]
    if case_plan.get('visual_evidence'):
        sources.append(repo/case_plan['visual_evidence'])
    for package in ('stationary_dna_v1','sound_dna','startup_catch_v1','phase_clock_v1'):
        sources+=list((repo/'tools'/package).glob('*.py'))
    for source in sources:
        relative=source.relative_to(repo);target=a.out/'exact_sources'/relative
        target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(source,target)
        r['sources'][relative.as_posix()]=sha(source)
    r.update(validation_report_sha256=sha(a.validated/'report.json'),plan_sha256=sha(plan_path))
    cases=case_plan['cases']
    for case in cases:
        train,heldout,info=inspect(a.qualified/case['id'],case,plan)
        r['cases'][case['id']]=info
        if info['stationary_scope_passed']:
            out=a.out/case['id'];root=info['acoustic_root_hz']
            info['candidate']=fit(train,root,plan,out,a.probe)
            sf.write(out/'train_reference.wav',physical_playback(train,root),48000,subtype='FLOAT')
            sf.write(out/'heldout_reference.wav',physical_playback(heldout,root),48000,subtype='FLOAT')
            generated,rate=sf.read(out/'detail.wav',always_2d=True);assert rate==48000
            generated_normalized=normalized_playback(generated,root)
            # Exclude the first second of statistical initialization. The
            # generated duration is independent of the reference duration.
            generated_normalized=generated_normalized[round(root/46.875*48000):]
            info['candidate']['heldout_vs_C_harmonic_observations']=difference(
                moments(heldout,root,plan['harmonics'],plan['bands_hz']),
                moments(generated_normalized,root,plan['harmonics'],plan['bands_hz']))
        else:
            info['candidate']=None
        print(json.dumps(dict(case=case['id'],root_hz=info['acoustic_root_hz'],
            stationary_scope_passed=info['stationary_scope_passed'],
            max_heldout_db=info['maximum_heldout_power_difference_db'],
            max_heldout_correlation=info['maximum_heldout_correlation_difference'],
            independent_halves=info['independent_halves'],candidate=info['candidate'] is not None)),flush=True)
    r.update(result='measured',generic_phase_qualification='not_passed_unchanged',
             original_local_gates=False,accepted_models_modified=False,default_modified=False)
except Exception as exc:
    r.update(result='failed',error=repr(exc));raise
finally:
    (a.out/'report.json').write_text(json.dumps(r,indent=2)+'\n',encoding='utf-8')
