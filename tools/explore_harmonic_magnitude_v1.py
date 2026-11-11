"""Offline high-harmonic magnitude candidate; accepted low/DNA stays immutable."""
import argparse
import json
from pathlib import Path
import shutil
import sys

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--workspace',type=Path,required=True)
parser.add_argument('--temporal',type=Path,required=True)
parser.add_argument('--out',type=Path,required=True)
args = parser.parse_args();repo=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(args.workspace/'tools/python_deps'))
import numpy as np
import soundfile as sf
from drive_evidence_v1.sources import sha
from harmonic_magnitude_v1 import model,legacy
from temporal_texture_v1.features import measure,summarize

args.out.mkdir(parents=True,exist_ok=False)
paths = [Path(__file__),repo/'tools/sustain_osc_v1/oracle.py',repo/'tools/drive_evidence_v1/sources.py',
    repo/'tools/temporal_texture_v1/features.py',*sorted((repo/'tools/harmonic_magnitude_v1').glob('*.py'))]
for path in paths:
    dest=args.out/'exact_sources'/path.relative_to(repo);dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(path,dest)
report=dict(schema='vsl.harmonic-magnitude-exploration/1',result='running',
    temporal_report_sha256=sha(args.temporal/'report.json'),source_sha256={p.relative_to(repo).as_posix():sha(p) for p in paths},
    trials=[],runtime_changed=False,human_accepted=False)
try:
    temporal=json.loads((args.temporal/'report.json').read_text(encoding='utf-8'))
    assert temporal['result']=='pass'
    plan=json.loads((args.temporal/'exact_sources/research/temporal_texture_v1_plan.json').read_text(encoding='utf-8'))
    frozen=args.workspace/'baselines/residual_motion_v1'
    manifest=json.loads((frozen/'manifest.json').read_text(encoding='utf-8'))
    assert sha(frozen/'manifest.json')==temporal['prior_manifest_sha256']
    entries={r['path']:r['sha256'] for r in manifest['files']}

    def read(name):
        path=frozen/name
        assert sha(path)==entries[name]
        x,rate=sf.read(path,always_2d=True);assert rate==48000 and np.isfinite(x).all()
        return x

    reference=read('evidence/fit1/reference.wav');base=read('evidence/fit1/accepted_pair.wav')
    coherent=args.workspace/'baselines/coherent_low_v1'
    cm=json.loads((coherent/'manifest.json').read_text(encoding='utf-8'))
    dna_path=coherent/'evidence/raw/dna.wav'
    assert sha(dna_path)==next(r['sha256'] for r in cm['files'] if r['path']=='evidence/raw/dna.wav')
    dna,rate=sf.read(dna_path,always_2d=True);assert rate==48000 and dna.shape==base.shape
    accepted=json.loads((repo/'research/coherent_low_v1_acceptance.json').read_text(encoding='utf-8'))
    profile=repo/'voices/dna_bank_v1/V10 Exterior.model'
    assert sha(profile)==accepted['dna_model_sha256']
    original=legacy.parse(profile)
    hz=np.arange(1,301)*46.875
    # Engineering transition, not a fitted engine crossover or a new EQ boost.
    u=np.clip((hz-1200)/(1900-1200),0,1);mask=.5-.5*np.cos(np.pi*u)
    old,old_high,phase=legacy.render(original,len(base),48271,mask)
    parity=float(abs(old-dna).max())
    assert parity<2e-7,parity
    candidate,stats=model.fit(reference)
    np.savez_compressed(args.out/'candidate_moments.npz',**candidate,fixed_phase=phase,mask=mask)
    target=measure(reference,plan)['covariance'].mean(axis=0)
    target_norm=np.maximum(np.linalg.norm(target,axis=(1,2)),1e-20)
    report.update(training=stats,legacy_C_max_abs_error=parity,model_sha256=sha(args.out/'candidate_moments.npz'),
        accepted_profile_sha256=sha(profile),prior_manifest_sha256=sha(frozen/'manifest.json'),
        source=dict(reference_sha256=sha(frozen/'evidence/fit1/reference.wav'),
            base_sha256=sha(frozen/'evidence/fit1/accepted_pair.wav'),dna_wav_sha256=sha(dna_path)),
        crossover_hz=[1200,1900],amounts=[.5,1],phase_policy='Accepted complex-mean phase; no PM/FM',
        power_policy='Per-sample ensemble E[A^2] normalization for interpolated Gaussian log magnitudes; no per-WAV normalization')

    # Independent known static magnitudes: exact expected sine sum.
    known=dict(rms=np.array([[.2,.2],[.1,.1]]),basis=np.zeros((2,0,2)),rho=np.zeros(0),
        root=np.zeros((2,2,2)),residual_rho=np.zeros(2))
    fixed=model.render(known,np.zeros((2,2)),4800,31,np.ones(2))
    time=np.arange(4800)/48000
    expected=.2*np.cos(2*np.pi*46.875*time)+.1*np.cos(2*np.pi*93.75*time)
    static_error=float(abs(fixed-expected[:,None]).max());assert static_error<1e-12
    report['static_control_max_error']=static_error
    warm=plan['generator_warmup_frames']
    for seed in (78283,41719,61927):
        new_high=model.render(candidate,phase,len(base),seed,mask)
        for amount in (.5,1.):
            audio=base+amount*(new_high-old_high)
            assert np.isfinite(audio).all()
            name=f'magnitude_{seed}_{amount:g}'
            sf.write(args.out/(name+'.wav'),audio,48000,subtype='FLOAT')
            data=measure(audio[warm:],plan);summary=summarize(data)
            distance=np.linalg.norm(data['covariance']-target[None,:],axis=(2,3))/target_norm
            record=dict(name=name,seed=seed,amount=amount,peak=float(abs(audio).max()),
                wav_sha256=sha(args.out/(name+'.wav')),summary=summary,
                covariance_relative_distance_median_LR=np.median(distance,axis=0).tolist())
            report['trials'].append(record)
            print(json.dumps(dict(name=name,distance=record['covariance_relative_distance_median_LR'],
                high_cv=summary['median_cv_LR'][6:],peak=record['peak'])),flush=True)
    report.update(result='pass',promotion_decision='offline_candidate_only',limits=[
        'Same1.217s normalized fixed A context; no unseen-recording, RPM/load/state generalization or listening acceptance',
        'All high harmonic magnitude statistics are replaced above the engineering crossover; this is not added residual AM',
        'Legacy fixed-phase oracle is checked against frozen C before subtraction; archived base has float rounding',
        'Gaussian log magnitude is unbounded and needs finite-run/peak/power/stereo qualification before a C implementation',
        'PCA/AR1 magnitude moments are approximate; phase and inter-harmonic residual remain separate limitations',
        'No C/model-bank/UI/driver/take changes; no native device or7.1.4 validation'])
except Exception as exc:
    report.update(result='failed',error=repr(exc));raise
finally:
    (args.out/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
print(json.dumps(dict(result=report['result'],legacy_C_error=parity,static_control_error=static_error)),flush=True)
