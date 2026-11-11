"""Compare frozen C stems and approved recordings without fitting a new sound."""
import argparse
import csv
import json
from pathlib import Path
import shutil
import subprocess
import sys

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--workspace',type=Path,required=True)
parser.add_argument('--out',type=Path,required=True)
args = parser.parse_args()
repo = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(args.workspace/'tools/python_deps'))
import numpy as np
import soundfile as sf
from drive_evidence_v1.sources import sha
from temporal_texture_v1.features import measure,phase_surrogate,scalar_power_check,summarize
from temporal_texture_v1.controls import run as known_controls

args.out.mkdir(parents=True,exist_ok=False)
plan_path = repo/'research/temporal_texture_v1_plan.json'
plan = json.loads(plan_path.read_text(encoding='utf-8'))
sources = [Path(__file__),plan_path,repo/'tools/drive_evidence_v1/sources.py',
           *sorted((repo/'tools/temporal_texture_v1').glob('*.py'))]
for path in sources:
    target = args.out/'exact_sources'/path.relative_to(repo)
    target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(path,target)
report = dict(schema='vsl.temporal-texture-analysis/1',result='running',
    plan_sha256=sha(plan_path),source_sha256={p.relative_to(repo).as_posix():sha(p) for p in sources},
    base_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=repo,text=True).strip(),
    observations=[],frozen_inputs={},raw_sources={},controls=[])
(args.out/'metadata.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')


def read_audio(path):
    x,rate = sf.read(path,dtype='float64',always_2d=True)
    assert rate==plan['sample_rate'] and x.shape[1]==2 and np.isfinite(x).all(),path
    return x


def observe(name,audio,kind,provenance,**extra):
    data = measure(audio,plan)
    assert data['parseval_error'].max()<plan['parseval_absolute_tolerance'],name
    direct = scalar_power_check(audio,data,plan)
    assert direct<plan['scalar_dft_relative_tolerance'],(name,direct)
    target = args.out/(name+'.npz')
    np.savez_compressed(target,**data)
    row = dict(name=name,kind=kind,provenance=provenance,input_frames=len(audio),
        ignored_tail_frames=len(audio)%plan['block_frames'],
        scalar_dft_relative_error=direct,observation_sha256=sha(target),summary=summarize(data),**extra)
    report['observations'].append(row)
    print(json.dumps(dict(name=name,blocks=row['summary']['blocks'],
        cv=[round(x[0],3) for x in row['summary']['median_cv_LR']],
        crossband=row['summary']['median_abs_crossband_correlation_LR'])),flush=True)
    return data,row


def compare(row, data, target):
    expected = target['covariance'].mean(axis=0)
    actual = data['covariance']
    distance = np.linalg.norm(actual-expected[None,:],axis=(2,3))
    norm = np.maximum(np.linalg.norm(expected,axis=(1,2)),1e-20)
    power = data['power'].mean(axis=(0,1))
    target_power = target['power'].mean(axis=(0,1))
    row['fixed_target_comparison'] = dict(
        covariance_relative_distance_median_LR=np.median(distance/norm,axis=0).tolist(),
        covariance_relative_distance_minmax_LR=np.array([np.min(distance/norm,axis=0),np.max(distance/norm,axis=0)]).tolist(),
        band_power_delta_db_LR=(10*np.log10(np.maximum(power,1e-30)/np.maximum(target_power,1e-30))).tolist(),
        scope='Same short normalized fixed-coordinate A target only; not a perceptual score or unseen recording test')


try:
    report['controls'] = known_controls(plan)
    print('known controls pass',flush=True)
    root = args.workspace/'baselines/residual_motion_v1'
    manifest = json.loads((root/'manifest.json').read_text(encoding='utf-8'))
    expected = {r['path']:r['sha256'] for r in manifest['files']}
    report['prior_manifest_sha256'] = sha(root/'manifest.json')
    report['prior_source_commit'] = manifest['source_commit']

    def frozen(name):
        path = root/name
        digest = sha(path)
        assert digest==expected[name],name
        report['frozen_inputs'][name] = digest
        return read_audio(path)

    reference = frozen('evidence/fit1/reference.wav')
    target,target_row = observe('fixed_A_reference',reference,'paired_reference',dict(
        file='evidence/fit1/reference.wav',root=str(root),
        processing='Existing normalized fixed acoustic coordinate; not raw audio or physical source separation'))
    base = frozen('evidence/fit1/accepted_pair.wav')
    warm = plan['generator_warmup_frames']
    data,row = observe('fixed_DNA_LF',base[warm:],'C_mix',dict(
        file='evidence/fit1/accepted_pair.wav',root=str(root),warmup_frames=warm))
    compare(row,data,target)
    for seed in plan['procedural_seeds']:
        raw_name = f'evidence/verification2/heldout_{seed}_raw.wav'
        am_name = f'evidence/verification2/heldout_{seed}.wav'
        raw,am = frozen(raw_name),frozen(am_name)
        assert raw.shape==am.shape==base.shape
        for suffix,audio,kind in (('static_solo',raw,'C_residual'),('AM_solo',am,'C_residual'),
                                 ('static_mix',base+raw,'C_mix'),('AM_mix',base+am,'C_mix')):
            data,row = observe(f'C_{seed}_{suffix}',audio[warm:],kind,dict(
                source_seed=seed,raw_file=raw_name,motion_file=am_name,root=str(root),warmup_frames=warm,
                mix='Float64 sum of unchanged frozen float32 stems' if suffix.endswith('mix') else 'Unchanged frozen C residual stem'))
            if kind=='C_mix':compare(row,data,target)
    for seed in plan['surrogate_seeds']:
        audio,spectral_error = phase_surrogate(reference,seed)
        assert spectral_error<plan['surrogate_relative_spectral_tolerance']
        data,row = observe(f'phase_surrogate_{seed}',audio,'offline_diagnostic',dict(
            seed=seed,input='fixed_A_reference',processing='Common random Fourier-bin phase rotation for L/R; not a runtime method'),
            complete_spectral_matrix_relative_error=spectral_error)
        compare(row,data,target)

    catalog_path = args.workspace/'references/segments_v1.json'
    catalog = json.loads(catalog_path.read_text(encoding='utf-8'))
    report['catalog_sha256'] = sha(catalog_path)
    for case in plan['recording_cases']:
        segment = catalog['segments'][case['segment']]
        assert case['use'] in segment['allowed_uses']
        assert segment['seconds'][0]<=case['seconds'][0]<case['seconds'][1]<=segment['seconds'][1]
        identity = segment['source'];source = catalog['sources'][identity]
        if identity not in report['raw_sources']:
            for key in ('raw','master'):
                assert sha(args.workspace/source[key])==source[key+'_sha256'],(identity,key)
            report['raw_sources'][identity] = {k:source[k] for k in ('raw','master','raw_sha256','master_sha256')}
        with sf.SoundFile(args.workspace/source['master']) as stream:
            assert stream.samplerate==48000 and stream.channels==2 and stream.subtype=='FLOAT'
            start,stop = [round(t*48000) for t in case['seconds']]
            stream.seek(start);audio = stream.read(stop-start,dtype='float64',always_2d=True)
        assert np.isfinite(audio).all()
        observe(case['name'],audio,'raw_recording',dict(case=case,source=identity,
            perspective=segment['perspective'],source_frame_bounds=[start,stop],
            processing='Unchanged raw decoded stereo; no gain, filtering, phase warp or resampling'))
    with (repo/'handoff/C文件索引.csv').open(encoding='utf-8-sig',newline='') as stream:
        index = list(csv.DictReader(stream))
    assert len(index)==436
    for row in index:
        assert sha(repo/row['文件'])==row['SHA-256'],row['文件']
    report.update(result='pass',c_h_count=len(index),c_index_sha256=sha(repo/'handoff/C文件索引.csv'),
        runtime_changed=False,models_changed=False,state_mapping_changed=False,human_accepted=False,
        promotion_decision='diagnostic_only',limits=[plan['scope'],
            'Fixed reference has one complete block; no confidence interval or engine/load identification',
            'Surrogate preserves whole-length spectral matrix, not local block power; it also randomizes coherent DNA phases',
            'Frozen C stems represent actual tested C output; no new C render, device or listening validation',
            'Normalized reference versus raw intervals are different coordinates; no exact matched-RPM comparison',
            'Recording L/R covariance is not a set of independently located physical objects'])
except Exception as exc:
    report.update(result='failed',error=repr(exc))
    raise
finally:
    (args.out/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
print(json.dumps(dict(result=report['result'],observations=len(report['observations']),controls=len(report['controls']))),flush=True)
