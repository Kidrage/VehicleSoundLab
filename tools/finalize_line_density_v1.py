"""Verify decoded artifacts/provenance and publish opt-in experimental profiles."""
import argparse
import csv
import importlib.util
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
from urllib.parse import quote,urljoin
from urllib.request import urlopen

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--workspace',type=Path,required=True)
parser.add_argument('--ffmpeg',type=Path,required=True)
parser.add_argument('--server',default='http://127.0.0.1:8789/')
args=parser.parse_args();repo=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(args.workspace/'tools/python_deps'))
import numpy as np
import soundfile as sf
from drive_evidence_v1.sources import sha
from residual_osc_v1.spectrum import matrices,error
from line_density_v1.measure import measure
from line_density_v1.controls import cases

root=args.workspace/'references/analysis/line_density_v1'
analysis=json.loads((root/'analysis2/report.json').read_text(encoding='utf-8'))
render=json.loads((root/'render1/report.json').read_text(encoding='utf-8'))
assert analysis['result']=='diagnostics_completed' and analysis['diagnostic_gate']['separate_experimental_C_render_eligible']
assert render['result']=='technical_pass_only' and render['technical_render_qualified'] and not render['human_accepted']
inputs={};attempts=[]
for name in ('analysis1','analysis2','render1'):
    record=json.loads((root/name/'report.json').read_text(encoding='utf-8'))
    for path,digest in record['source_sha256'].items():assert sha(root/name/'exact_sources'/path)==digest,(name,path)
    for path,digest in record['input_sha256'].items():assert sha(path)==digest,path
    inputs.update(record['input_sha256'])
    attempts.append(dict(folder=name,result=record['result'],error=record.get('error')))
assert attempts[0]['result']=='failed'
for record in (analysis,render):
    for path,digest in record['source_sha256'].items():assert sha(repo/path)==digest,path
for ob in analysis['observations']:assert sha(root/'analysis2'/(ob['name']+'.npz'))==ob['arrays_sha256']
plan=json.loads((repo/'research/line_density_v1_plan.json').read_text(encoding='utf-8'))
archive=np.load(args.workspace/'baselines/temporal_texture_v1/evidence/magnitude1/candidate_moments.npz')
fixed=cases(archive['rms'],archive['fixed_phase'],58424,plan)[0][1]
old_path=root/'analysis1/exact_sources/tools/line_density_v1/measure.py'
spec=importlib.util.spec_from_file_location('failed_line_density_oracle',old_path)
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
old_error=module.measure(fixed,plan,8)[0]['direct_DFT_relative_error']
new_error=measure(fixed,plan,8)[0]['direct_DFT_relative_error']
assert old_error>plan['tolerances']['direct_DFT_relative']>new_error
assert sha(root/'analysis1/exact_sources/research/line_density_v1_plan.json')==sha(root/'analysis2/exact_sources/research/line_density_v1_plan.json')
reference,rate=sf.read(args.workspace/'baselines/residual_motion_v1/evidence/fit1/reference.wav',always_2d=True)
assert rate==48000
target=matrices(reference);decoded=[];concentrations={}
for trial in render['trials']:
    for seed in trial['seeds']:
        path=root/'render1/raw'/(trial['name']+'_'+str(seed['seed'])+'_mix.wav')
        assert sha(path)==seed['mixed_sha256']
        audio,rate=sf.read(path,always_2d=True);assert rate==48000 and len(audio)==768000
        actual=max(abs(v) for row in error(target,matrices(audio[24000:])) for v in row['power_delta_db'])
        difference=abs(actual-seed['maximum_power_error_db']);assert difference<1e-5
        decoded.append(dict(amount=trial['amount'],seed=seed['seed'],decoded_power_error_db=actual,reported_error_difference_db=difference))
        if seed['seed']==8121907:
            row,_=measure(audio[24000:24000+len(reference)],plan,16)
            concentrations[trial['name']]=row['rows'][0]['concentration_LR']
url=quote(urljoin(args.server,'research/高频密度对照V1.html'),safe=':/')
with urlopen(url,timeout=15) as response:
    assert response.status==200;page_bytes=response.read()
assert page_bytes==(args.workspace/'research/高频密度对照V1.html').read_bytes()
sources=re.findall(r'<audio[^>]*src="([^"]+)"',page_bytes.decode('utf-8'))
assert len(sources)==len(set(sources))==7
audio_checks=[]
for relative in sources:
    audio_url=urljoin(url,relative)
    local=root/'render1/audition'/Path(relative).name
    with urlopen(audio_url,timeout=15) as response:
        assert response.status==200 and response.read()==local.read_bytes()
    result=subprocess.run([str(args.ffmpeg),'-v','error','-i',str(local),'-f','null','-'],capture_output=True,text=True,timeout=30)
    assert result.returncode==0,(local,result.stderr)
    info=sf.info(local);assert info.samplerate==48000 and info.frames==384000 and info.channels==2 and info.subtype=='PCM_24'
    audio_checks.append(dict(file=local.name,sha256=sha(local),HTTP_bytes_exact=True,FFmpeg_decodes=True))
with (repo/'handoff/C文件索引.csv').open(encoding='utf-8-sig',newline='') as stream:index=list(csv.DictReader(stream))
assert len(index)==436
for row in index:assert sha(repo/row['文件'])==row['SHA-256'],row['文件']
verification=dict(schema='vsl.line-density-verification/1',result='pass',
    failed_oracle_reproduced_relative_error=old_error,corrected_oracle_relative_error=new_error,plan_thresholds_unchanged=True,
    decoded_mixes=decoded,audition_checks=audio_checks,browser_interaction_checked=False,human_listening_checked=False,
    c_h_count=len(index),c_index_sha256=sha(repo/'handoff/C文件索引.csv'))
(root/'verification.json').write_text(json.dumps(verification,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
destination=repo/'voices/line_density_v1';destination.mkdir(exist_ok=False)
entries=[]
for trial in render['trials']:
    amount=round(trial['amount']*100);name='V10 A Density '+str(amount)
    residual=destination/(name+'.residual');shutil.copy2(root/'render1/models'/(trial['name']+'.residual'),residual)
    if amount:
        dna=destination/(name+'.model');shutil.copy2(root/'render1/models'/(trial['name']+'.model'),dna)
    else:dna=repo/'voices/dna_bank_v1/V10 Exterior.model'
    entries.append(dict(amount=trial['amount'],dna=dna.relative_to(repo).as_posix(),residual=residual.relative_to(repo).as_posix(),
        dna_sha256=sha(dna),residual_sha256=sha(residual)))
bank=dict(schema='vsl.line-density-experimental/1',context='A moving-tailpipe316.10..317.25s, fixed46.875Hz coordinate',
    status='unaccepted_opt_in_experiment',default_driver_attached=False,human_accepted=False,
    low='voices/coherent_low_v1/measured_phase.model',low_scale=1.6658265329883064,entries=entries)
(destination/'index.json').write_text(json.dumps(bank,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
source_paths=[Path(__file__),repo/'tools/freeze_line_density_v1.py',repo/'tools/analyze_line_density_v1.py',
    repo/'tools/render_line_density_v1.py',repo/'research/line_density_v1_plan.json',repo/'research/line_density_render_v1_plan.json',
    *sorted((repo/'tools/line_density_v1').glob('*.py'))]
summary=dict(schema='vsl.line-density-summary/1',date='2026-11-12',result='experimental_C_render_only',evidence_root=str(root),
    attempts=attempts,diagnostic_gate=analysis['diagnostic_gate'],
    diagnostic_maximum_DFT_relative=max(row['direct_DFT_relative_error'] for ob in analysis['observations'] for row in ob['configurations']),
    diagnostic_maximum_parseval_relative=max(row['parseval_relative_error'] for ob in analysis['observations'] for row in ob['configurations']),
    maximum_direct_C_subtraction_error=max(row['maximum_C_subtraction_error'] for row in render['trials']),
    maximum_candidate_power_error_db=max(row['maximum_power_error_db'] for trial in render['trials'] if trial['amount']>0 for row in trial['seeds']),
    maximum_complex_coherence_error=max(row['maximum_complex_coherence_error'] for trial in render['trials'] for row in trial['seeds']),
    maximum_coherence_projection_excess=max(float(np.hypot(*row['unclipped_coherence'])-1) for trial in render['trials'] for row in trial['residual_rows']),
    fixed_reference_concentration=next(ob for ob in analysis['observations'] if ob['name']=='fixed_A_reference')['configurations'][1]['rows'][0]['concentration_LR'],
    C_review_seed_concentrations=concentrations,review_url=url,review_page_sha256=render['review_page_sha256'],
    original_C_stem_exact=True,frozen_low_stem_preserved=True,authored_experimental_profiles=entries,
    C_changes=False,default_models_changed=False,driver_changes=False,human_accepted=False,
    c_h_count=len(index),c_index_sha256=verification['c_index_sha256'],
    current_source_sha256={p.relative_to(repo).as_posix():sha(p) for p in source_paths},
    evidence_sha256={p.relative_to(root).as_posix():sha(p) for p in sorted(root.rglob('*')) if p.is_file() and '__pycache__' not in p.parts},
    input_sha256=inputs,limits=analysis['limits']+render['limits']+[
        'Original direct-DFT null-bin precision failure is retained/reproduced; integer modular phase correction changed the oracle, not the plan threshold',
        'Low profile rows and independent LF stem are invariant; high-harmonic AM sidebands can still affect lowpass mixed audio',
        'HTTP byte checks/FFmpeg decoding do not prove browser interaction or perceived naturalness',
        'Existing magnitude listening remains pending; this separate page creates no duplicate question or implied acceptance'])
(repo/'research/line_density_v1_summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
print(json.dumps(dict(result=summary['result'],max_candidate_power_error_db=summary['maximum_candidate_power_error_db'],
    direct_error=summary['maximum_direct_C_subtraction_error'],profiles=len(entries),audio_files=len(audio_checks))),flush=True)
