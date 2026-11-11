"""Known stereo/power and decoded candidate checks for the offline AR8 voice."""
import argparse
import json
from pathlib import Path
import shutil
import sys

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--workspace',type=Path,required=True)
parser.add_argument('--candidate',type=Path,required=True)
parser.add_argument('--out',type=Path,required=True)
args=parser.parse_args();repo=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(args.workspace/'tools/python_deps'))
import numpy as np
import soundfile as sf
from drive_evidence_v1.sources import sha
from magnitude_timescale_v1.render import render
from residual_osc_v1.spectrum import matrices
from common_envelope_v1.features import band_power,analyze,summarize,scalar_power_check

args.out.mkdir(parents=True,exist_ok=False)
paths=[Path(__file__),repo/'tools/drive_evidence_v1/sources.py',repo/'tools/magnitude_timescale_v1/render.py',
    repo/'tools/magnitude_timescale_v1/factors.py',repo/'tools/common_envelope_v1/features.py',
    repo/'tools/residual_osc_v1/spectrum.py']
for path in paths:
    target=args.out/'exact_sources'/path.relative_to(repo)
    target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(path,target)
report=dict(schema='vsl.factor-ar8-verification/1',result='running',
    source_sha256={p.relative_to(repo).as_posix():sha(p) for p in paths},
    candidate_report_sha256=sha(args.candidate/'report.json'),controls=[],trials=[],gate_failures=[])
(args.out/'metadata.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')

try:
    candidate=json.loads((args.candidate/'report.json').read_text(encoding='utf-8'));assert candidate['result']=='pass'
    for name,digest in candidate['source_sha256'].items():assert sha(args.candidate/'exact_sources'/name)==digest
    archive=np.load(args.candidate/'factor_profiles.npz')
    profiles=[{k:archive[k][j] for k in archive.files} for j in (0,2)]
    h=100;active=np.array([25,40,63,99]);amounts=np.array([[.15,.1],[-.12,.18],[.20,-.05],[-.10,-.15]])
    known=dict(rms=np.zeros((h,2)),basis=np.zeros((h,2,2)),root=np.zeros((h,2,2)),residual_rho=np.zeros(h))
    known['rms'][active]=[.1,.07];known['basis'][active]=amounts[:,:,None]
    phase=np.zeros((h,2));phase[:,1]=.4
    bands=[[1100,1350],[1800,2050],[2800,3200],[4500,4900]]
    for seed in (11031,62017,95179):
        audio=render(known,profiles,phase,16*48000,seed,np.ones(h))
        observed=matrices(audio,bands=bands);power_error=[];coherence_error=[]
        for row in observed:
            p=np.array(row['power']);power_error.extend((10*np.log10(p/(np.array([.1,.07])**2/2))).tolist())
            coherence=complex(*row['cross'])/np.sqrt(np.prod(p))
            coherence_error.append(float(abs(coherence-np.exp(.4j))))
        if max(map(abs,power_error))>=.5:
            report['gate_failures'].append(dict(seed=seed,gate='16s_per_run_power_error_below_0p5dB',maximum_error=max(map(abs,power_error))))
        if max(coherence_error)>=.005:
            report['gate_failures'].append(dict(seed=seed,gate='complex_coherence_error_below_0p005',maximum_error=max(coherence_error)))
        report['controls'].append(dict(seed=seed,power_error_db=power_error,complex_coherence_error=coherence_error,frames=len(audio)))
        print(json.dumps(dict(seed=seed,maximum_power_error_db=max(map(abs,power_error)),maximum_complex_coherence_error=max(coherence_error))),flush=True)
    known['rms'][:,1]=known['rms'][:,0]
    mono=render(known,profiles,np.zeros((h,2)),48000,811,np.ones(h))
    assert np.array_equal(mono[:,0],mono[:,1]);report['exact_mono']=True
    # Read every actual FLOAT file again and recompute the saved power/shape
    # statistics with a direct trigonometric DFT check on selected windows.
    plan=json.loads((repo/'research/common_envelope_v1_plan.json').read_text(encoding='utf-8'))
    plan.update(block_seconds=[1],offset_fractions=[0],detrend_orders=[1])
    for row in candidate['trials']:
        path=args.candidate/row['path'];assert sha(path)==row['sha256']
        audio,rate=sf.read(path,always_2d=True);assert rate==48000 and audio.shape==(384000,2) and np.isfinite(audio).all()
        starts,power=band_power(audio[plan['warmup_frames']:],plan)
        direct=scalar_power_check(audio[plan['warmup_frames']:],starts,power,plan);assert direct<1e-10
        summary=summarize(analyze(starts,power,len(audio)-plan['warmup_frames'],plan))
        old=row['measurement']['summary'][0]['medians'];actual=summary[0]['medians']
        error=max(float(np.max(abs(np.array(actual[key])-old[key]))) for key in actual)
        assert error==0,error
        report['trials'].append(dict(seed=row['seed'],sha256=sha(path),direct_DFT_relative_error=direct,
            maximum_summary_error=error,peak=float(abs(audio).max())))
    report.update(result='not_passed' if report['gate_failures'] else 'pass',all_checks_executed=True,runtime_changes=False,human_accepted=False,
        limits=['Known finite-run power/stereo, mono and decoded-WAV arithmetic only; no timbre, runtime or recording-generalization acceptance',
                'Prototype Gaussian log amplitudes remain unbounded; existing frozen review and accepted models remain authoritative'])
except Exception as exc:
    report.update(result='failed',error=repr(exc));raise
finally:
    (args.out/'report.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
print(json.dumps(dict(result=report['result'],controls=len(report['controls']),trials=len(report['trials']))))
