"""Fit one additive stereo residual-color candidate using unchanged DNA and Rvs C."""
import argparse
import os
from pathlib import Path
import shutil
import subprocess
import sys

p=argparse.ArgumentParser(description=__doc__)
for key in ('workspace','observation','out','dna-probe','stereo-probe'):p.add_argument('--'+key,type=Path,required=True)
a=p.parse_args();repo=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(a.workspace/'tools/python_deps'))
for key in ('OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','OMP_NUM_THREADS'):os.environ[key]='2'
import numpy as np
import soundfile as sf
from scipy import linalg
from scipy.optimize import nnls
from research_archive_v1 import load,save,sha
from residual_osc_v1.spectrum import matrices,error
from stereo_resonance_v1.model import matrix,predictor,fit,density,measured,pack,export

a.out.mkdir(parents=True,exist_ok=False)
r=dict(result='running',sources={},inputs={},models=[],skipped=[],commands=[],trials=[])

def consume(path):r['inputs'][str(path)]=sha(path);return path

def run(argv,label):
    argv=list(map(str,argv));done=subprocess.run(argv,cwd=repo,capture_output=True,timeout=180)
    path=a.out/(label+'.log');path.write_bytes(done.stdout+done.stderr)
    r['commands'].append(dict(argv=argv,exit_code=done.returncode,log=path.name))
    save(a.out/'report.json',r);assert done.returncode==0,path
    return done.stdout

try:
    names=['tools/fit_F3_detail_v1.py','research/F3_detail_v1_plan.json',
        'tools/stereo_resonance_v1/model.py','tools/residual_osc_v1/spectrum.py','tools/research_archive_v1.py',
        'experiments/stereo_resonance_v1/probe.c','experiments/sound_dna_export_v1/probe.c']
    for package in ('sound_dna','stereo_resonance','stereo_resonance_io','resonant_detail'):
        names += [p.relative_to(repo).as_posix() for p in (repo/'modules'/package).glob('*') if p.is_file()]
    for name in names:
        dest=a.out/'exact_sources'/name;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(repo/name,dest);r['sources'][name]=sha(repo/name)
    plan=load(consume(repo/'research/F3_detail_v1_plan.json'))
    # Known lag/cross-sign controls before reference reads or fitting.
    coef=np.array([[[.23,.04],[-.06,-.18]],[[.08,-.02],[.03,.05]],[[-.04,.01],[.02,.03]]])
    noise=np.array([[.3,0],[.17,.2]]);f=np.zeros((6,6));f[:2]=coef.transpose(1,0,2).reshape(2,6);f[2:,:-2]=np.eye(4)
    q=np.zeros((6,6));q[:2,:2]=noise@noise.T;stationary=linalg.solve_discrete_lyapunov(f,q)
    gamma=np.array([(np.linalg.matrix_power(f,k)@stationary)[:2,:2] for k in range(4)])
    recovered,innovation=predictor(gamma,3)
    err=max(float(abs(recovered-coef).max()),float(abs(innovation@innovation.T-noise@noise.T).max()))
    assert err<plan['gates']['known_predictor_FS']
    delayed=np.zeros((3,2,2));delayed[2,1,0]=.6
    fixture=dict(a=delayed.tolist(),noise=[[1,0],[0,.8]],sos=[[1,0,0,1,0,0]])
    spectrum=density(fixture);hz=np.arange(len(spectrum))*48000/len(spectrum)
    signed=float(abs(spectrum[:,1,0]-.6*np.exp(-2j*np.pi*hz*3/48000)/48000).max())
    assert signed<plan['gates']['known_signed_density_FS2_per_Hz']
    r['known_before_source']=dict(predictor_error=err,signed_delay_density_error=signed)
    observation=load(consume(a.observation/'report.json'));assert observation['result']=='fixed_residual_observed'
    source=a.workspace/'baselines/F3_lift_voice_v1/evidence/fit2/F3 Sixth Before Upshift'
    root=observation['root_hz'];bands=plan['bands_hz']
    reference,rate=sf.read(consume(source/'reference.wav'),always_2d=True);assert rate==48000
    color,rate=sf.read(consume(a.observation/'residual_reference.wav'),always_2d=True);assert rate==48000
    assert subprocess.check_output([str(a.dna_probe),'--describe'],text=True).strip()=='vsl.sound-dna-raw-export/1'
    consume(a.dna_probe);consume(a.stereo_probe);consume(source/'voice.model')
    (a.out/'bin').mkdir();shutil.copy2(a.dna_probe,a.out/'bin/sound_dna_export.exe');shutil.copy2(a.stereo_probe,a.out/'bin/stereo_resonance_probe.exe')
    run([a.dna_probe,source/'voice.model',a.out/'main32.wav',plan['statistics_seconds'],1,1,plan['DNA_seed'],512],'main32')
    main,rate=sf.read(a.out/'main32.wav',always_2d=True);old,oldrate=sf.read(consume(source/'DNA_1.wav'),always_2d=True)
    assert rate==oldrate==48000 and np.array_equal(main[:len(old)],old)
    # Keep the frozen eight-second training main for the debt definition; long main is diagnostic.
    target=np.array([matrix(v) for v in matrices(reference,bands)])
    current=np.array([matrix(v) for v in matrices(old[24000:],bands)]);debt=target-current
    predictions=[]
    for band,wanted in zip(bands,debt):
        eigen=np.linalg.eigvalsh(wanted)
        if min(eigen)<=0:r['skipped'].append(dict(band=band,reason='Indefinite additive debt',eigenvalues=eigen.tolist()));continue
        try:model=fit(color,band,wanted,plan['kernel'])
        except ValueError as exc:r['skipped'].append(dict(band=band,reason=str(exc)));continue
        predictions.append(measured(density(model),bands));r['models'].append(model)
        save(a.out/'report.json',r);print(dict(band=band,pole_radius=model['pole_radius']),flush=True)
    assert r['models'],'No fixed-policy model passed'
    design=np.stack([pack(v).ravel() for v in predictions],axis=1)
    scale=pack(target).copy();scale[:,2:]=np.sqrt(scale[:,0]*scale[:,1])[:,None];scale=1/scale.ravel()
    gain,_=nnls(design*scale[:,None],pack(debt).ravel()*scale)
    for model,value in zip(r['models'],gain):model['gain']=float(np.sqrt(value))
    expected=sum(g*v for g,v in zip(gain,predictions))
    save(a.out/'matrices.json',dict(target=pack(target).tolist(),DNA=pack(current).tolist(),debt=pack(debt).tolist(),expected_detail=pack(expected).tolist()))
    profile=a.out/'F3_before_upshift.sres';export(profile,r['models'],root)
    for seed in plan['detail_seeds']:
        output=a.out/f'detail32_{seed}.f64';run([a.stereo_probe,profile,output,seed,len(main),1],f'detail_{seed}')
        detail=np.fromfile(output,dtype='<f8').reshape(-1,2)
        assert detail.shape==main.shape and np.isfinite(detail).all() and not np.array_equal(detail[:48000],detail[48000:96000])
        actual=np.array([matrix(v) for v in matrices(detail,bands)]);diagnostic=[]
        for wanted,got in zip(expected,actual):
            power=(10*np.log10(got.diagonal().real/wanted.diagonal().real)).tolist()
            c=got[1,0]/np.sqrt(got[0,0]*got[1,1]);d=wanted[1,0]/np.sqrt(wanted[0,0]*wanted[1,1])
            diagnostic.append(dict(power_error_db=power,complex_coherence_error=float(abs(c-d))))
        assert max(abs(v) for row in diagnostic for v in row['power_error_db'])<plan['gates']['C_theory_power_db']
        assert max(v['complex_coherence_error'] for v in diagnostic)<plan['gates']['C_theory_complex_coherence']
        mixed=main+detail;assert abs(mixed).max()*.5<plan['gates']['peak_after_common_gain']
        count=plan['audition_seconds']*48000
        sf.write(a.out/f'candidate_{seed}.wav',mixed[:count],48000,subtype='FLOAT')
        sf.write(a.out/f'detail_{seed}.wav',detail[:count],48000,subtype='FLOAT')
        short=error(matrices(reference,bands),matrices(mixed[24000:count],bands))
        r['trials'].append(dict(seed=seed,C_theory=diagnostic,short_mixed_vs_reference=short,
            maximum_power_error_db=max(abs(v) for row in short for v in row['power_delta_db']),
            maximum_complex_coherence_error=max(row['complex_coherence_error'] for row in short),peak_FS=float(abs(mixed).max())))
        save(a.out/'report.json',r);print(dict(seed=seed,maximum_power_db=r['trials'][-1]['maximum_power_error_db']),flush=True)
    r.update(result='fixed_additive_residual_candidate_rendered',root_hz=root,profile_sha256=sha(profile),
        same_DNA=True,withdrawal=0,room=False,periodic_residual_modulation=False,
        physical_source_separation=False,human_accepted=False,runtime_changed=False)
except Exception as exc:r.update(result='failed',error=repr(exc));raise
finally:save(a.out/'report.json',r)
