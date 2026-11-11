"""Known stereo/power controls and actual candidate WAV checks, no deployment."""
import argparse
import csv
import json
from pathlib import Path
import shutil
import sys

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--workspace',type=Path,required=True)
parser.add_argument('--root',type=Path,required=True)
parser.add_argument('--out',type=Path,required=True)
args=parser.parse_args();repo=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(args.workspace/'tools/python_deps'))
import numpy as np
import soundfile as sf
from drive_evidence_v1.sources import sha
from harmonic_magnitude_v1.model import render
from residual_osc_v1.spectrum import matrices
from temporal_texture_v1.features import measure,scalar_power_check,summarize

args.out.mkdir(parents=True,exist_ok=False)
paths=[Path(__file__),repo/'tools/harmonic_magnitude_v1/model.py',repo/'tools/residual_osc_v1/spectrum.py',
       repo/'tools/temporal_texture_v1/features.py',repo/'tools/drive_evidence_v1/sources.py']
for path in paths:
    target=args.out/'exact_sources'/path.relative_to(repo);target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(path,target)
report=dict(schema='vsl.harmonic-magnitude-offline-verification/1',result='running',
    source_sha256={p.relative_to(repo).as_posix():sha(p) for p in paths},controls=[],trials=[])
try:
    report['temporal_report_sha256']=sha(args.root/'analysis1/report.json')
    report['candidate_report_sha256']=sha(args.root/'magnitude1/report.json')
    candidate=json.loads((args.root/'magnitude1/report.json').read_text(encoding='utf-8'))
    temporal=json.loads((args.root/'analysis1/report.json').read_text(encoding='utf-8'))
    assert candidate['result']==temporal['result']=='pass'
    for root,result in ((args.root/'analysis1',temporal),(args.root/'magnitude1',candidate)):
        for name,digest in result['source_sha256'].items():assert sha(root/'exact_sources'/name)==digest
    h=100;active=np.array([25,40,63,99]);amounts=np.array([[.15,.1],[-.12,.18],[.20,-.05],[-.10,-.15]])
    known=dict(rms=np.zeros((h,2)),basis=np.zeros((h,2,2)),rho=np.array([.9,.6]),
        root=np.zeros((h,2,2)),residual_rho=np.zeros(h))
    known['rms'][active]=[.1,.07]
    known['basis'][active]=amounts[:,:,None]
    phase=np.zeros((h,2));phase[:,1]=.4
    bands=[[1100,1350],[1800,2050],[2800,3200],[4500,4900]]
    for seed in (11031,62017,95179):
        audio=render(known,phase,16*48000,seed,np.ones(h))
        observed=matrices(audio,bands=bands)
        power_error=[];coherence_error=[]
        for row in observed:
            p=np.array(row['power']);power_error.extend((10*np.log10(p/(np.array([.1,.07])**2/2))).tolist())
            coherence=complex(*row['cross'])/np.sqrt(np.prod(p))
            coherence_error.append(float(abs(coherence-np.exp(.4j))))
        assert max(map(abs,power_error))<.5,(seed,power_error)
        assert max(coherence_error)<.005,(seed,coherence_error)
        report['controls'].append(dict(seed=seed,power_error_db=power_error,complex_coherence_error=coherence_error,
            frames=len(audio),bands=observed,expected_carrier_phase_difference_radians=.4))
        print('known stereo/power',seed,'pass',flush=True)
    # Exact mono is a separate structural condition, not inferred from the
    # approximately preserved nonzero complex-coherence control above.
    known['rms'][:,1]=known['rms'][:,0]
    mono=render(known,np.zeros((h,2)),48000,811,np.ones(h))
    assert np.array_equal(mono[:,0],mono[:,1])
    report['exact_mono_passed']=True
    plan=json.loads((args.root/'analysis1/exact_sources/research/temporal_texture_v1_plan.json').read_text(encoding='utf-8'))
    target=np.load(args.root/'analysis1/fixed_A_reference.npz')['covariance'].mean(axis=0)
    norm=np.maximum(np.linalg.norm(target,axis=(1,2)),1e-20)
    warm=plan['generator_warmup_frames']
    for row in candidate['trials']:
        path=args.root/'magnitude1'/(row['name']+'.wav');assert sha(path)==row['wav_sha256']
        x,rate=sf.read(path,always_2d=True);assert rate==48000 and x.shape==(384000,2) and np.isfinite(x).all()
        data=measure(x[warm:],plan);summary=summarize(data)
        direct=scalar_power_check(x[warm:],data,plan);assert direct<plan['scalar_dft_relative_tolerance']
        cv_error=float(abs(np.array(summary['median_cv_LR'])-row['summary']['median_cv_LR']).max())
        assert cv_error<1e-6,cv_error
        distance=np.median(np.linalg.norm(data['covariance']-target[None,:],axis=(2,3))/norm,axis=0)
        assert abs(distance-row['covariance_relative_distance_median_LR']).max()<1e-6
        np.savez_compressed(args.out/(row['name']+'.npz'),**data)
        report['trials'].append(dict(name=row['name'],wav_sha256=sha(path),scalar_dft_relative_error=direct,
            maximum_float32_cv_drift=cv_error,peak=float(abs(x).max()),summary=summary,
            covariance_relative_distance_median_LR=distance.tolist()))
    with (repo/'handoff/C文件索引.csv').open(encoding='utf-8-sig',newline='') as stream:index=list(csv.DictReader(stream))
    assert len(index)==436
    for row in index:assert sha(repo/row['文件'])==row['SHA-256'],row['文件']
    accepted=json.loads((repo/'research/coherent_low_v1_acceptance.json').read_text(encoding='utf-8'))
    assert sha(repo/accepted['model'])==accepted['model_sha256']
    assert sha(repo/'voices/dna_bank_v1/V10 Exterior.model')==accepted['dna_model_sha256']
    report.update(result='pass',c_h_count=len(index),c_index_sha256=sha(repo/'handoff/C文件索引.csv'),
        accepted_models_unchanged=True,models_changed=False,runtime_changed=False,human_accepted=False,
        limits=['Known-model finite-run power/stereo and decoded WAV arithmetic only; not C runtime or perceptual validation',
                'Candidate statistics still use the same short normalized recording; no independent real-engine validation',
                'Unbounded lognormal amplitudes and amplitude-only sidebands need further qualification before C/UI adoption'])
except Exception as exc:
    report.update(result='failed',error=repr(exc));raise
finally:
    (args.out/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
print(json.dumps(dict(result=report['result'],controls=len(report['controls']),trials=len(report['trials']),c_h_count=len(index))),flush=True)
