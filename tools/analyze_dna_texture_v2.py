"""Audit the source of harmonic texture; no synthesis/default/model changes."""
import argparse,csv,json,shutil,sys
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--workspace',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
a=p.parse_args();repo=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(a.workspace/'tools/python_deps'))
import numpy as np
import soundfile as sf
from dna_texture_v2.observe import observe
from dna_texture_v2.controls import run
from drive_evidence_v1.sources import sha

a.out.mkdir(parents=True,exist_ok=False)
paths=[Path(__file__),repo/'research/dna_texture_v2_plan.json',*sorted((repo/'tools/dna_texture_v2').glob('*.py'))]
for path in paths:
    target=a.out/'exact_sources'/path.relative_to(repo);target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(path,target)
plan=json.loads((repo/'research/dna_texture_v2_plan.json').read_text(encoding='utf-8'))
r=dict(schema='vsl.dna-texture-diagnostic/1',result='running',plan=plan,source_sha256={str(p.relative_to(repo)):sha(p) for p in paths},input_sha256={})
try:
    r['known_controls']=run(plan)
    root=a.workspace/'references/analysis/phase_texture_c_v1/verification1'
    cases=[('A_normalized_reference',a.workspace/'baselines/residual_motion_v1/evidence/fit1/reference.wav',0),
           ('DNA_original',root/'seed_8121907_amount_0/dna.wav',24000),
           ('DNA_rejected_C_light',root/'seed_8121907_amount_1/dna.wav',24000)]
    observations=[]
    for name,path,offset in cases:
        if name=='A_normalized_reference':
            manifest=a.workspace/'baselines/residual_motion_v1/manifest.json'
            expected=next(v['sha256'] for v in json.loads(manifest.read_text(encoding='utf-8'))['files'] if v['path']=='evidence/fit1/reference.wav')
            assert sha(path)==expected
        r['input_sha256'][str(path)]=sha(path)
        x,rate=sf.read(path,always_2d=True);assert rate==48000
        x=x[offset:offset+58424];assert x.shape==(58424,2)
        rows=observe(x,plan)
        assert max(b['direct_correlation_relative_error'] for b in rows)<plan['controls']['direct_correlation_error']
        observations.append(dict(name=name,first_frame=offset,frames=len(x),bands=rows))
        print(json.dumps(dict(name=name,repeat_1cycle_L=[round(b['repeat'][0]['maximum_repeat'],4) for b in rows],
            envelope_pass=[b['periodic_envelope_gate_passed'] for b in rows])),flush=True)
    r['observations']=observations
    with (repo/'handoff/C文件索引.csv').open(encoding='utf-8-sig') as f:index=list(csv.DictReader(f))
    assert len(index)==478
    for row in index:assert sha(repo/row['文件'])==row['SHA-256'],row['文件']
    r.update(result='diagnostics_pass',C_H_unchanged=478,Ctests_not_repeated=True,no_audio_candidate=True,
        causal_limit='Repeat/periodic envelopes describe this normalized recording; they do not identify physical friction, cylinder events or a unique audible cause')
except Exception as exc:r.update(result='failed',error=repr(exc));raise
finally:(a.out/'report.json').write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
(repo/'research/dna_texture_v2_summary.json').write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
print(json.dumps(dict(result=r['result'],known_control=r['known_controls']['result'],unchanged_C_H=478)))
