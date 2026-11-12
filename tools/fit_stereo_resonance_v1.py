"""Fit an independent A cabin-settling detail candidate, preserving stereo debt."""
import argparse, csv, json, shutil, sys
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--workspace',type=Path,required=True); p.add_argument('--out',type=Path,required=True)
a=p.parse_args(); repo=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(a.workspace/'tools/python_deps'))
import numpy as np
import soundfile as sf
import scipy
from scipy.optimize import nnls
from drive_evidence_v1.sources import read,sha
from residual_osc_v1.spectrum import matrices
from stereo_resonance_v1.model import matrix,fit,density,measured,pack,export
a.out.mkdir(parents=True,exist_ok=False)
r=dict(result='running',sources={},inputs={},models=[],skipped=[],
       runtime=dict(python=sys.version,numpy=np.__version__,scipy=scipy.__version__,soundfile=sf.__version__),
       plan=dict(order=24,spectral_smoothing_hz=50,covariance_ridge=.0001,max_pole_radius=.9998,
                 taper_fraction=.1,postfilter_order=4,fft_frames=65536,
                 policy='Fit once; preserve non-PSD bands and failed attempts. No listening-quality pass from mean powers.'))
try:
    for path in [Path(__file__),repo/'tools/stereo_resonance_v1/model.py',repo/'tools/drive_evidence_v1/sources.py',repo/'tools/residual_osc_v1/spectrum.py']:
        target=a.out/'exact_sources'/path.relative_to(repo); target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(path,target); r['sources'][path.relative_to(repo).as_posix()]=sha(path)
    summary=json.loads((repo/'research/startup_catch_v1_summary.json').read_text(encoding='utf-8'))
    proof=a.workspace/'references/analysis/startup_catch_v1/slow3/report.json'
    assert sha(proof)==summary['evidence_sha256']['slow3/report.json']
    proven=json.loads(proof.read_text()); assert all(v['passed'] for v in proven['pairs'])
    source=a.workspace/'references/analysis/startup_catch_v1/render1/renders/fixed_1.0.wav'
    assert sha(source)==summary['evidence_sha256']['render1/renders/fixed_1.0.wav']
    main,rate=sf.read(source,always_2d=True); assert rate==48000
    main=main[96000:]; root=summary['model']['base_hz']
    assert sha(repo/'voices/startup_settle_v1/A start cabin settle.model')==summary['model']['sha256']
    x,meta=read(a.workspace,'A_start_context','audio_onset_observation')
    x=x[round((38.48-33)*48000):round((39.51-33)*48000)]
    sf.write(a.out/'reference.wav',x,48000,subtype='FLOAT'); sf.write(a.out/'DNA.wav',main,48000,subtype='FLOAT')
    for path in [proof,source,repo/'research/startup_catch_v1_summary.json',repo/'voices/startup_settle_v1/A start cabin settle.model']:
        r['inputs'][str(path)]=sha(path)
    bands=[[400,600],[600,850],[850,1200],[1200,1600],[1600,2200],[2200,3000],[3000,4000],[4000,6000],[6000,8000]]
    target=np.array([matrix(v) for v in matrices(x,bands)])
    current=np.array([matrix(v) for v in matrices(main,bands)])
    debt=target-current; prediction=[]
    for band,d in zip(bands,debt):
        eigen=np.linalg.eigvalsh(d)
        if min(eigen)<=0:
            r['skipped'].append(dict(band=band,debt_eigenvalues=eigen.tolist(),reason='Non-PSD additive debt; no clipping or harmonic attenuation'))
            continue
        model=fit(x,band,d,r['plan'])
        prediction.append(measured(density(model),bands))
        r['models'].append(model)
        print(json.dumps(dict(band=band,pole=model['pole_radius'],certificate_margin=model['certificate_margin'])),flush=True)
    design=np.stack([pack(v).ravel() for v in prediction],axis=1)
    scale=pack(target).copy(); scale[:,2:]=np.sqrt((scale[:,0]*scale[:,1]))[:,None]
    scale=1/scale.ravel()
    gain,_=nnls(design*scale[:,None],pack(debt).ravel()*scale)
    predicted=current+sum(g*v for g,v in zip(gain,prediction))
    for model,g in zip(r['models'],gain):model['gain']=float(np.sqrt(g))
    profile=a.out/'A cabin settle.sres'; export(profile,r['models'],root)
    covariance=[]
    for band,t,q in zip(bands,target,predicted):
        ct=t[1,0]/np.sqrt(t[0,0]*t[1,1]); cq=q[1,0]/np.sqrt(q[0,0]*q[1,1])
        covariance.append(dict(band=band,power_error_db=(10*np.log10(q.diagonal().real/t.diagonal().real)).tolist(),complex_coherence_error=float(abs(ct-cq))))
    r.update(result='stereo_candidate_fitted_not_listened',source=meta,source_seconds=[38.48,39.51],root_hz=root,
        profile_sha256=sha(profile),prediction=covariance,main_model_unchanged=True,room_added=False,
        no_runtime_integration=True,full_idle_or_acceleration_calibrated=False,
        limits=['Startup-settling cabin recording, not hot idle or exterior transfer',
                '600..850Hz non-PSD debt cannot be filled by an independent additive layer',
                'One short training context; no independent engine/load or listening acceptance'])
except Exception as exc:r.update(result='failed',error=repr(exc)); raise
finally:(a.out/'report.json').write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
