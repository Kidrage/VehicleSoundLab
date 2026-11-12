"""Verify and preserve the accepted-baseline phase trial and rejected-HF feedback."""
import argparse
import csv
import json
from pathlib import Path
import shutil
import sys
import urllib.request

p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--workspace',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
a=p.parse_args();repo=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(a.workspace/'tools/python_deps'))
import numpy as np
import soundfile as sf
from drive_evidence_v1.sources import sha

a.out.mkdir(parents=True,exist_ok=False)
root=a.workspace/'references/analysis/phase_texture_v1';trial=root/'trial2'
r=dict(schema='vsl.phase-texture-verification/1',result='running',human_accepted=False)
try:
    record=json.loads((trial/'report.json').read_text(encoding='utf-8'))
    assert record['result']=='offline_common_HF_phase_candidate_rendered'
    failed=json.loads((root/'trial1/report.json').read_text(encoding='utf-8'))
    assert failed['result']=='failed' and 'broadcast' in failed['error']
    for name,digest in record['source_sha256'].items():assert sha(repo/name)==sha(trial/'exact_sources'/name)==digest,name
    for name,digest in record['input_sha256'].items():assert sha(name)==digest,name
    assert not record['strength_policy']['source_phase_qualified']
    assert len(record['trials'])==6 and len(record['clips'])==4
    for row in record['clips']:
        path=trial/row['file'];assert sha(path)==row['sha256'] and row['http_decode']
    for row in record['trials']:
        path=trial/f'raw_{row["seed"]}_{row["amount"]:g}.wav';assert sha(path)==row['raw_sha256']
        assert row['maximum_power_change_db']<.01
        assert row['motion_below4Hz_power_fraction']<.001
        assert row['delay_bound_microseconds']<=8*row['amount']
    # Read actual disk outputs and compare independent reference audio. This
    # catches accidental use of a different duration, baseline or clip gain.
    dna,rate=sf.read(a.workspace/'baselines/coherent_low_v1/evidence/raw/dna.wav',always_2d=True)
    low,rate2=sf.read(a.workspace/'baselines/coherent_low_v1/evidence/raw/measured.wav',always_2d=True)
    assert rate==rate2==48000
    baseline=(dna+1.6658265329883064*low[:len(dna)])[24000:384000]
    y,rate=sf.read(trial/'accepted_original.wav',always_2d=True)
    expected=baseline*.5;n=240;fade=np.sin(np.linspace(0,np.pi/2,n))**2
    expected[:n]*=fade[:,None];expected[-n:]*=fade[::-1,None]
    quantization_error=float(np.max(abs(y-expected)));assert quantization_error<=2**-23
    with (repo/'handoff/C文件索引.csv').open(encoding='utf-8-sig') as stream:index=list(csv.DictReader(stream))
    for row in index:assert sha(repo/row['文件'])==row['SHA-256'],row['文件']
    page=trial/'index.html';url='http://127.0.0.1:8789/'+page.relative_to(a.workspace).as_posix()
    with urllib.request.urlopen(url,timeout=10) as response:assert response.read()==page.read_bytes()
    r.update(result='pass',C_H_unchanged=len(index),accepted_baseline_PCM24_max_error_FS=quantization_error,
             new_CTests_run=False,device_checked=False,browser_interaction=False,
             page_sha256=sha(page),page=url,source_phase_calibration='not_passed')
except Exception as exc:r.update(result='failed',error=repr(exc));raise
finally:(a.out/'report.json').write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')

docs=['AGENTS.md','README.md','research/听评记录.md','research/hf_bandwidth_v1_listening.json',
      'research/主声线共同微扰V1.md','handoff/声纹沉淀与控制边界.md']
tools=['tools/try_phase_texture_v1.py','tools/finalize_phase_texture_v1.py',
       'tools/phase_texture_v1/source.py','tools/phase_texture_v1/render.py']
def hashes(folder):return {p.relative_to(folder).as_posix():sha(p) for p in sorted(folder.rglob('*')) if p.is_file() and '__pycache__' not in p.parts}
summary=dict(schema='vsl.phase-texture-summary/1',date='2026-11-12',result='offline_hypothesis_listening_only',
    latest_user_feedback=json.loads((repo/'research/hf_bandwidth_v1_listening.json').read_text(encoding='utf-8')),
    source_phase_observation=record['source_phase_observation'],strength_policy=record['strength_policy'],
    known_controls=record['known_controls'],trials=record['trials'],clips=record['clips'],verification=r,
    runtime_changed=False,human_accepted=False,limits=record['limits'],
    input_sha256=record['input_sha256'],current_source_sha256={name:sha(repo/name) for name in docs+tools},
    evidence_sha256=hashes(root))
summary_path=repo/'research/phase_texture_v1_summary.json'
summary_path.write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
freeze=a.workspace/'baselines/phase_texture_v1'
assert freeze.resolve().is_relative_to(a.workspace.resolve()) and not freeze.exists()
shutil.copytree(root,freeze/'evidence',ignore=shutil.ignore_patterns('__pycache__'))
for name in docs+tools+['research/phase_texture_v1_summary.json']:
    dest=freeze/'source'/name;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(repo/name,dest)
manifest=dict(schema='vsl.freeze/1',files=[dict(path=name,sha256=digest) for name,digest in hashes(freeze).items()])
(freeze/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
for row in manifest['files']:assert sha(freeze/row['path'])==row['sha256']
print(json.dumps(dict(result=r['result'],C_H=r['C_H_unchanged'],freeze_files=len(manifest['files']),source_calibration=r['source_phase_calibration'])))
