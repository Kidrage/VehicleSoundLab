"""Assess shared gain versus colour in existing recordings; no model fitting."""
import argparse
import csv
import json
from pathlib import Path
import shutil
import subprocess
import sys

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--workspace',type=Path,required=True)
parser.add_argument('--out',type=Path,required=True)
args=parser.parse_args();repo=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(args.workspace/'tools/python_deps'))
import numpy as np
import soundfile as sf
from drive_evidence_v1.sources import sha
from common_envelope_v1.features import band_power,analyze,summarize,scalar_power_check
from common_envelope_v1.controls import run as known_controls

args.out.mkdir(parents=True,exist_ok=False)
plan_path=repo/'research/common_envelope_v1_plan.json'
plan=json.loads(plan_path.read_text(encoding='utf-8'))
sources=[Path(__file__),plan_path,repo/'tools/drive_evidence_v1/sources.py',
         *sorted((repo/'tools/common_envelope_v1').glob('*.py'))]
for path in sources:
    target=args.out/'exact_sources'/path.relative_to(repo)
    target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(path,target)
report=dict(schema='vsl.common-envelope-analysis/1',result='running',
    base_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=repo,text=True).strip(),
    plan_sha256=sha(plan_path),source_sha256={p.relative_to(repo).as_posix():sha(p) for p in sources},
    controls=[],observations=[],frozen_inputs={},raw_sources={})
(args.out/'metadata.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')


def save_control(name,starts,power,data):
    np.savez_compressed(args.out/('control_'+name+'.npz'),starts=starts,power=power,**data)


def observe(name,audio,provenance):
    assert audio.ndim==2 and audio.shape[1]==2 and np.isfinite(audio).all()
    starts,power=band_power(audio,plan)
    direct=scalar_power_check(audio,starts,power,plan)
    assert direct<plan['tolerances']['direct_dft_relative'],(name,direct)
    rows=analyze(starts,power,len(audio),plan)
    for row in rows:
        for key in ('decomposition_relative_error','slow_decomposition_relative_error'):
            assert row[key]<plan['tolerances']['decomposition_relative'],(name,key,row[key])
        assert row['parseval_relative_error']<plan['tolerances']['parseval_relative']
        assert row['floored_band_frames']==0,(name,row['floored_band_frames'])
    target=args.out/(name+'.npz')
    np.savez_compressed(target,starts=starts,power=power)
    report['observations'].append(dict(name=name,provenance=provenance,input_frames=len(audio),
        source_power_sha256=sha(target),direct_dft_relative_error=direct,
        rows=rows,summary=summarize(rows)))
    selected=[r for r in summarize(rows) if r['block_seconds']==1 and r['offset_fraction']==0 and r['detrend_order']==1]
    print(json.dumps(dict(name=name,blocks=len(rows),one_second_linear=selected)),flush=True)


try:
    report['controls']=known_controls(plan,save_control)
    print('Known common-gain/colour/pitch controls pass',flush=True)
    prior=args.workspace/'baselines/residual_motion_v1'
    manifest=json.loads((prior/'manifest.json').read_text(encoding='utf-8'))
    expected={r['path']:r['sha256'] for r in manifest['files']}
    report['prior_manifest_sha256']=sha(prior/'manifest.json')
    for name,file,warm in (
        ('fixed_A_reference','evidence/fit1/reference.wav',0),
        ('accepted_DNA_LF','evidence/fit1/accepted_pair.wav',plan['warmup_frames'])):
        path=prior/file;digest=sha(path);assert digest==expected[file]
        report['frozen_inputs'][str(path)]=digest
        audio,rate=sf.read(path,dtype='float64',always_2d=True)
        assert rate==plan['sample_rate']
        observe(name,audio[warm:],dict(kind='frozen',file=str(path),warmup_frames=warm,
            coordinates='normalized fixed acoustic reference' if warm==0 else 'accepted fixed-coordinate C generator'))
    # Candidate analysis is observational, never a listening acceptance.
    prior=args.workspace/'baselines/temporal_texture_v1'
    manifest=json.loads((prior/'manifest.json').read_text(encoding='utf-8'))
    expected={r['path']:r['sha256'] for r in manifest['files']}
    report['temporal_manifest_sha256']=sha(prior/'manifest.json')
    for amount in (50,100):
        file=f'evidence/magnitude1/magnitude_78283_{amount}.wav'
        # Bind the exact predeclared listening seed via the original trial record.
        trials=json.loads((prior/'evidence/magnitude1/report.json').read_text(encoding='utf-8'))['trials']
        trial=next(r for r in trials if r['seed']==78283 and r['amount']==amount/100)
        file='evidence/magnitude1/'+trial['name']+'.wav'
        path=prior/file;digest=sha(path);assert digest==expected[file]
        report['frozen_inputs'][str(path)]=digest
        audio,rate=sf.read(path,dtype='float64',always_2d=True);assert rate==plan['sample_rate']
        observe('candidate_'+str(amount),audio[plan['warmup_frames']:],dict(
            kind='offline_unaccepted_candidate',file=str(path),seed=78283,amount=amount/100,
            warmup_frames=plan['warmup_frames']))
    catalog_path=args.workspace/'references/segments_v1.json'
    catalog=json.loads(catalog_path.read_text(encoding='utf-8'))
    report['catalog_sha256']=sha(catalog_path)
    for case in plan['recording_cases']:
        segment=catalog['segments'][case['segment']]
        assert case['use'] in segment['allowed_uses']
        assert segment['seconds'][0]<=case['seconds'][0]<case['seconds'][1]<=segment['seconds'][1]
        identity=segment['source'];source=catalog['sources'][identity]
        if identity not in report['raw_sources']:
            for key in ('raw','master'):assert sha(args.workspace/source[key])==source[key+'_sha256']
            report['raw_sources'][identity]={k:source[k] for k in ('raw','master','raw_sha256','master_sha256')}
        with sf.SoundFile(args.workspace/source['master']) as stream:
            assert stream.samplerate==48000 and stream.channels==2 and stream.subtype=='FLOAT'
            start,stop=[round(t*48000) for t in case['seconds']]
            stream.seek(start);audio=stream.read(stop-start,dtype='float64',always_2d=True)
        observe(case['name'],audio,dict(kind='raw_recording',case=case,source=identity,
            perspective=segment['perspective'],source_frame_bounds=[start,stop],
            processing='No gain, filtering, phase warp or resampling'))
    with (repo/'handoff/C文件索引.csv').open(encoding='utf-8-sig',newline='') as stream:index=list(csv.DictReader(stream))
    assert len(index)==436
    for row in index:assert sha(repo/row['文件'])==row['SHA-256'],row['文件']
    acceptance=json.loads((repo/'research/coherent_low_v1_acceptance.json').read_text(encoding='utf-8'))
    assert sha(repo/acceptance['model'])==acceptance['model_sha256']
    assert sha(repo/'voices/dna_bank_v1/V10 Exterior.model')==acceptance['dna_model_sha256']
    report.update(result='pass',c_h_count=len(index),c_index_sha256=sha(repo/'handoff/C文件索引.csv'),
        runtime_changes=False,models_changed=False,state_mapping_changed=False,new_human_acceptance=False,
        decision='measurement_only; no causal separation or runtime promotion',limits=[plan['scope'],
        'The fixed normalized reference has only one full 1s block; it cannot establish sub-Hz statistics',
        'Common band motion may arise from gain, pitch, motion, recording transfer or the source; no causal labels',
        'Removing common log gain also removes legitimate common source motion; shape is not stationary engine texture',
        'Detrending and overlapping segmentation are sensitivity variants, not independent evidence or significance tests',
        'Existing image evidence shows moving-tailpipe context, but does not prove an unedited audio track or constant load',
        'Recording L/R remain observations, not two located physical sources'])
except Exception as exc:
    report.update(result='failed',error=repr(exc));raise
finally:
    (args.out/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
print(json.dumps(dict(result=report['result'],controls=len(report['controls']),observations=len(report['observations']))),flush=True)
