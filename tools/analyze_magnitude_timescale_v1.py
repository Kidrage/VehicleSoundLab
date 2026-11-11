"""Quantify old AR clipping and clock confounds; export one offline contrast."""
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
from harmonic_magnitude_v1.model import render
from harmonic_magnitude_v1.legacy import parse,render as old_render
from magnitude_timescale_v1.statistics import inspect,describe,known_ar
from magnitude_timescale_v1.clock import make as clock_controls
from common_envelope_v1.features import band_power,analyze,summarize,scalar_power_check

args.out.mkdir(parents=True,exist_ok=False)
plan_path=repo/'research/magnitude_timescale_v1_plan.json';plan=json.loads(plan_path.read_text(encoding='utf-8'))
paths=[Path(__file__),plan_path,repo/'tools/drive_evidence_v1/sources.py',
    repo/'tools/harmonic_magnitude_v1/model.py',repo/'tools/harmonic_magnitude_v1/legacy.py',
    repo/'tools/sustain_osc_v1/oracle.py',repo/'tools/exterior_clock_v1/warp.py',
    repo/'tools/common_envelope_v1/features.py',*sorted((repo/'tools/magnitude_timescale_v1').glob('*.py'))]
for path in paths:
    target=args.out/'exact_sources'/path.relative_to(repo)
    target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(path,target)
report=dict(schema='vsl.magnitude-timescale/1',result='running',source_sha256={p.relative_to(repo).as_posix():sha(p) for p in paths},
    base_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=repo,text=True).strip(),
    input_sha256={},trials=[],clock_controls=[],known_ar=[])
(args.out/'metadata.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')


def frozen(root,name):
    manifest=json.loads((root/'manifest.json').read_text(encoding='utf-8'))
    path=root/name;assert sha(path)==next(r['sha256'] for r in manifest['files'] if r['path']==name),name
    report['input_sha256'][str(path)]=sha(path)
    report['input_sha256'][str(root/'manifest.json')]=sha(root/'manifest.json')
    return path


def read(path):
    x,rate=sf.read(path,dtype='float64',always_2d=True);assert rate==48000 and x.shape[1]==2 and np.isfinite(x).all()
    return x


def measure(audio):
    starts,power=band_power(audio,measurement)
    error=scalar_power_check(audio,starts,power,measurement)
    assert error<plan['tolerances']['direct_dft_relative'],error
    return dict(summary=summarize(analyze(starts,power,len(audio),measurement)),direct_dft_relative_error=error,
        phase_and_magnitude_observations=describe(audio,plan['phase_observation_orders']))


try:
    prior=args.workspace/'baselines/temporal_texture_v1'
    model_path=frozen(prior,'evidence/magnitude1/candidate_moments.npz')
    archive=np.load(model_path);original={k:archive[k] for k in ('rms','basis','rho','root','residual_rho')}
    phase,mask=archive['fixed_phase'],archive['mask']
    motion=args.workspace/'baselines/residual_motion_v1'
    reference=read(frozen(motion,'evidence/fit1/reference.wav'))
    base=read(frozen(motion,'evidence/fit1/accepted_pair.wav'))
    measurement_path=repo/'research/common_envelope_v1_plan.json'
    report['input_sha256'][str(measurement_path)]=sha(measurement_path)
    measurement=json.loads(measurement_path.read_text(encoding='utf-8'))
    measurement.update(block_seconds=[1],offset_fractions=[0],detrend_orders=[1])
    warm=measurement['warmup_frames']
    report['reference']=measure(reference)
    changed,stats=inspect(reference,original,plan['diagnostic_rho_cap'])
    assert stats['old_rho_recovery_max_error']<plan['tolerances']['recovered_existing_rho_absolute'],stats['old_rho_recovery_max_error']
    report['statistics']=stats
    np.savez_compressed(args.out/'diagnostic_moments.npz',**changed,fixed_phase=phase,mask=mask)
    report['known_ar']=known_ar(plan)
    report['cap_decay_seconds']={str(cap):-256/48000/float(np.log(cap)) for cap in (.95,.99)}
    ridge_path=args.workspace/'references/analysis/sustain_osc_v1/ridge_observations.npz'
    coherent=args.workspace/'baselines/coherent_low_v1'
    coherent_report=json.loads(frozen(coherent,'evidence/report.json').read_text(encoding='utf-8'))
    assert sha(ridge_path)==coherent_report['source']['ridge_sha256']
    report['input_sha256'][str(ridge_path)]=sha(ridge_path)
    rows,outputs,positions=clock_controls(np.load(ridge_path),plan)
    for row,audio in zip(rows,outputs):
        name='clock_'+str(row['clock_fractional_error'])
        sf.write(args.out/(name+'.wav'),audio,48000,subtype='FLOAT')
        row.update(file=name+'.wav',sha256=sha(args.out/(name+'.wav')),band_observations=measure(audio))
    np.savez_compressed(args.out/'clock_positions.npz',source_seconds=positions)
    report['clock_controls']=rows
    print(json.dumps(dict(cap_seconds=report['cap_decay_seconds'],factor_variance_above_cap=stats['factor_variance_fraction_above_old_cap'],
        known_clock_high_errors=[r['high_harmonic_magnitude_rms_error_db_LR'] for r in rows])),flush=True)
    accepted=json.loads((repo/'research/coherent_low_v1_acceptance.json').read_text(encoding='utf-8'))
    profile=repo/'voices/dna_bank_v1/V10 Exterior.model'
    assert sha(profile)==accepted['dna_model_sha256'] and sha(repo/accepted['model'])==accepted['model_sha256']
    report['input_sha256'][str(profile)]=sha(profile)
    old,old_high,old_phase=old_render(parse(profile),len(base),48271,mask)
    dna=read(frozen(coherent,'evidence/raw/dna.wav'))
    error=float(abs(old-dna).max());assert error<plan['tolerances']['legacy_C_absolute']
    assert np.array_equal(phase,old_phase)
    report['legacy_C_max_error']=error
    for seed in plan['procedural_seeds']:
        old_file=frozen(prior,f'evidence/magnitude1/magnitude_{seed}_1.wav')
        old_audio=read(old_file)
        new_high=render(changed,phase,len(base),seed,mask)
        candidate=base+(new_high-old_high)
        path=args.out/f'rho99_{seed}.wav';sf.write(path,candidate,48000,subtype='FLOAT')
        decoded=read(path)
        report['trials'].append(dict(seed=seed,only_model_changes=['rho','residual_rho'],
            path=path.name,sha256=sha(path),peak=float(abs(decoded).max()),
            old=measure(old_audio[warm:]),candidate=measure(decoded[warm:])))
        print(json.dumps(dict(seed=seed,peak=report['trials'][-1]['peak'])),flush=True)
    with (repo/'handoff/C文件索引.csv').open(encoding='utf-8-sig',newline='') as stream:index=list(csv.DictReader(stream))
    assert len(index)==436
    for row in index:assert sha(repo/row['文件'])==row['SHA-256'],row['文件']
    report.update(result='pass',c_h_count=len(index),c_index_sha256=sha(repo/'handoff/C文件索引.csv'),
        runtime_changes=False,model_bank_changes=False,new_state_mapping=False,human_accepted=False,
        qualification='offline sensitivity only; no runtime or perceptual promotion',limits=[plan['scope'],
            'Exactly tracked synthetic oscillators do not prove the real acoustic clock is exact',
            'Short-window real carrier phase includes source/transfer/interference; no true clock-error inference',
            'A one-step AR fit/cap cannot identify missing multi-scale dynamics from one short recording',
            'The changed lognormal amplitude remains unbounded; mean expected power is not a per-WAV peak guarantee',
            'This stage does not resolve source/state causality, high-frequency realism or stereo width'])
except Exception as exc:
    report.update(result='failed',error=repr(exc));raise
finally:
    (args.out/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps(dict(result=report['result'],trials=len(report['trials']),known_clock_controls=len(report['clock_controls']))),flush=True)
