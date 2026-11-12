"""Qualify stereo recurrence/IO and measure the actual C candidate, without a listening verdict."""
import argparse,csv,json,re,shutil,subprocess,sys,time
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__)
for name in ('workspace','build','fit','out'):p.add_argument('--'+name,type=Path,required=True)
a=p.parse_args();repo=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(a.workspace/'tools/python_deps'))
import numpy as np
import soundfile as sf
from scipy import linalg,signal
from drive_evidence_v1.sources import sha
from residual_osc_v1.spectrum import matrices,error
from stereo_resonance_v1.model import predictor,density,measured,matrix,export
from sustain_osc_v1.oracle import Gaussian
a.out.mkdir(parents=True,exist_ok=False)
r=dict(result='running',sources={},commands=[],controls={},trials=[],
       checks=dict(long_power_tolerance_db=.75,long_complex_coherence_tolerance=.08,
                   known_predictor_absolute=1e-11,known_C_absolute=2e-11),
       listening_accepted=False,driver_integrated=False)
def run(argv,expected=0,timeout=600):
    started=time.perf_counter();done=subprocess.run(list(map(str,argv)),cwd=repo,capture_output=True,timeout=timeout)
    path=a.out/f'command_{len(r["commands"]):02}.log';path.write_bytes(done.stdout+done.stderr)
    r['commands'].append(dict(argv=list(map(str,argv)),exit=done.returncode,expected=expected,
        seconds=time.perf_counter()-started,log=path.name,sha256=sha(path)))
    print(json.dumps(dict(command=str(argv[0]),exit=done.returncode,log=str(path))),flush=True)
    assert done.returncode==expected,(argv,done.returncode,path)
    return done.stdout
def covariance_errors(target,actual):
    return [dict(power_db=(10*np.log10(q.diagonal().real/t.diagonal().real)).tolist(),
        coherence_error=float(abs(q[1,0]/np.sqrt(q[0,0]*q[1,1])-t[1,0]/np.sqrt(t[0,0]*t[1,1])))) for t,q in zip(target,actual)]
def companion(coef):
    n=2*len(coef);f=np.zeros((n,n));f[:2]=coef.transpose(1,0,2).reshape(2,n);f[2:,:-2]=np.eye(n-2);return f
try:
    fit=json.loads((a.fit/'report.json').read_text(encoding='utf-8'))
    assert fit['result']=='stereo_candidate_fitted_not_listened'
    for name,digest in fit['sources'].items():assert sha(repo/name)==digest,name
    for name,digest in fit['inputs'].items():assert sha(Path(name))==digest,name
    profile=a.fit/'A cabin settle.sres';assert sha(profile)==fit['profile_sha256']
    with (repo/'handoff/C文件索引.csv').open(encoding='utf-8-sig') as f:prior=list(csv.DictReader(f))
    assert len(prior)==521
    for row in prior:assert sha(repo/row['文件'])==row['SHA-256'],row['文件']
    shutil.copy2(repo/'handoff/C文件索引.csv',a.out/'prior_C_index.csv')
    r['prior_C_H_unchanged']=521;r['fit_report_sha256']=sha(a.fit/'report.json')
    paths=[repo/row['文件'] for row in prior]
    for folder in ('modules/stereo_resonance','modules/stereo_resonance_io','experiments/stereo_resonance_v1'):
        paths.extend((repo/folder).glob('*.c'));paths.extend((repo/folder).glob('*.h'))
    r['C_H_rows']=len(paths);assert len(paths)==529
    paths.extend([Path(__file__),repo/'handoff/CMakeLists.txt',repo/'tools/stereo_resonance_v1/model.py',
        repo/'tools/sustain_osc_v1/oracle.py',repo/'tools/residual_osc_v1/spectrum.py',repo/'tools/drive_evidence_v1/sources.py'])
    paths.extend((repo/'modules').rglob('CMakeLists.txt'))
    for path in dict.fromkeys(paths):
        name=path.relative_to(repo).as_posix();dest=a.out/'exact_sources'/name;dest.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(path,dest);r['sources'][name]=sha(path)
    run(['cmake','--build',a.build,'--config','Release','--parallel','4'])
    tests=run(['ctest','--test-dir',a.build,'-C','Release','--parallel','4','--output-on-failure'])
    assert re.search(rb'100% tests passed(?:, 0 tests failed)? out of 52',tests);r['Ctests_passed']=52
    buildtext=(a.out/'command_00.log').read_text(encoding='utf-8',errors='replace').lower()
    assert not any(v in buildtext for v in ('warning c','error c','warning lnk','error lnk'))
    shutil.copy2(a.build/'CMakeCache.txt',a.out/'CMakeCache.after_build.txt')
    (a.out/'bin').mkdir()
    for name in ('VslStereoResonance_probe','VslSoundDna_probe'):
        shutil.copy2(a.build/'bin/Release'/f'{name}.exe',a.out/'bin'/f'{name}.exe')
    probe=a.out/'bin/VslStereoResonance_probe.exe'
    # An independent multichannel stationary state covariance recovers every
    # cross-lag coefficient, testing Gamma sign/order rather than fitting noise.
    coef=np.array([[[.23,.04],[-.06,-.18]],[[.08,-.02],[.03,.05]],[[-.04,.01],[.02,.03]]])
    noise=np.array([[.3,0],[.17,.2]]);f=companion(coef);q=np.zeros_like(f);q[:2,:2]=noise@noise.T
    stationary=linalg.solve_discrete_lyapunov(f,q)
    gamma=np.array([(np.linalg.matrix_power(f,k)@stationary)[:2,:2] for k in range(4)])
    recovered,innovation=predictor(gamma,3)
    pe=float(abs(recovered-coef).max());ne=float(abs(innovation@innovation.T-noise@noise.T).max())
    assert max(pe,ne)<r['checks']['known_predictor_absolute']
    r['controls']['known_VAR3_predictor']=dict(coefficient_error=pe,innovation_covariance_error=ne)
    # Delay direction fixture: R[n]=.6*L[n-3]+.8*v[n]. Its signed CSD is known.
    delayed=np.zeros((3,2,2));delayed[2,1,0]=.6
    dm=dict(a=delayed.tolist(),noise=[[1,0],[0,.8]],sos=[[1,0,0,1,0,0]])
    sd=density(dm);hz=np.arange(len(sd))*48000/len(sd)
    ce=float(abs(sd[:,1,0]-.6*np.exp(-2j*np.pi*hz*3/48000)/48000).max())
    swapped=dict(dm,a=delayed[:,::-1,::-1].tolist(),noise=[[.8,0],[0,1]])
    swap=float(abs(density(swapped)-sd[:,::-1,::-1]).max())
    assert max(ce,swap)<1e-18
    rr=np.random.default_rng(317);white=rr.standard_normal((960000,2));known=np.column_stack((white[:,0],.8*white[:,1]))
    known[3:,1]+=.6*white[:-3,0]
    broad=[[400,3000],[3000,8000],[8000,16000]]
    known_errors=covariance_errors(measured(sd,broad),np.array([matrix(v) for v in matrices(known,broad)]))
    assert max(abs(x) for row in known_errors for x in row['power_db'])<.2
    assert max(row['coherence_error'] for row in known_errors)<.03
    r['controls']['signed_delay_channel_swap']=dict(density_error=ce,swap_error=swap,Welch=known_errors)
    # Cross-platform known C output versus a separately indexed Python recurrence
    # and scipy SOS, using order3 cross-lags and a nontrivial postfilter.
    cert=linalg.solve_discrete_lyapunov(f.T,np.eye(6));cert/=np.diag(cert).max()
    fixture=dict(a=coef.tolist(),noise=noise.tolist(),certificate=cert.tolist(),gain=.8,band_hz=[400,800],
        sos=[[.4,-.1,.03,1,-.3,.08]])
    fixture_path=a.out/'fixture.sres';export(fixture_path,[fixture],35)
    output=a.out/'fixture.f64';run([probe,fixture_path,output,619,4096,1])
    streams=[Gaussian(619^(0x9E3779B97F4A7C15*(i+1)&((1<<64)-1))) for i in range(2)]
    z=np.array([[v.next() for v in streams] for _ in range(96000+4096)])
    state=np.zeros((len(z)+3,2))
    for n in range(len(z)):
        state[n+3]=noise@z[n]
        for k in range(3):state[n+3]+=coef[k]@state[n+2-k]
    oracle=.8*signal.sosfilt(fixture['sos'],state[3:],axis=0)[96000:]
    actual=np.fromfile(output,dtype='<f8').reshape(-1,2);delta=float(abs(actual-oracle).max())
    assert delta<r['checks']['known_C_absolute'];r['controls']['known_C_VAR3_SOS_error']=delta
    # Profile-level unstable/truncated cases exercise the actual loader/probe.
    broken=dict(fixture,a=(coef*20).tolist());bad=a.out/'unstable.sres';export(bad,[broken],35)
    run([probe,bad,a.out/'must_not_exist.f64',619,4096,1],expected=2)
    assert not (a.out/'must_not_exist.f64').exists()
    # The SAME unchanged DNA generator, extended forward, never looped.
    rawmain=a.out/'DNA_50s.wav'
    run([a.out/'bin/VslSoundDna_probe.exe',repo/'voices/startup_settle_v1/A start cabin settle.model',rawmain,50,1,1,1])
    main,rate=sf.read(rawmain,always_2d=True);assert rate==48000 and main.shape==(2400000,2)
    frozen,rate=sf.read(a.workspace/'references/analysis/startup_catch_v1/render1/renders/fixed_1.0.wav',always_2d=True)
    assert np.array_equal(main[:len(frozen)],frozen);r['DNA_first8s_exact_to_frozen']=True;main=main[96000:]
    reference,rate=sf.read(a.fit/'reference.wav',always_2d=True);assert rate==48000
    bands=[[400,600],[600,850],[850,1200],[1200,1600],[1600,2200],[2200,3000],[3000,4000],[4000,6000],[6000,8000]]
    detail_expected=sum(m['gain']**2*measured(density(m),bands) for m in fit['models'])
    previous=None
    for seed in (8121907,8121919,8121931):
        path=a.out/f'detail_{seed}.f64';perf=json.loads(run([probe,profile,path,seed,len(main),1]))
        y=np.fromfile(path,dtype='<f8').reshape(-1,2);assert y.shape==main.shape and np.isfinite(y).all()
        assert not np.array_equal(y[:48000],y[48000:96000])
        if previous is not None:assert not np.array_equal(y[:48000],previous)
        previous=y[:48000].copy()
        diagnostic=covariance_errors(detail_expected,np.array([matrix(v) for v in matrices(y,bands)]))
        assert max(abs(x) for row in diagnostic for x in row['power_db'])<r['checks']['long_power_tolerance_db']
        assert max(row['coherence_error'] for row in diagnostic)<r['checks']['long_complex_coherence_tolerance']
        mixed=main+y;active=[v for i,v in enumerate(error(matrices(reference,bands),matrices(mixed,bands))) if i!=1]
        low=error(matrices(main,[(20,300)]),matrices(mixed,[(20,300)]))[0]
        sf.write(a.out/f'mix_{seed}.wav',mixed[:288000],48000,subtype='FLOAT')
        sf.write(a.out/f'detail_{seed}.wav',y[:288000],48000,subtype='FLOAT')
        r['trials'].append(dict(seed=seed,frames=len(main),C_vs_theory=diagnostic,
            mixed_vs_reference=error(matrices(reference,bands),matrices(mixed,bands)),
            supported_max_power_error_db=max(abs(v) for row in active for v in row['power_delta_db']),
            supported_max_coherence_error=max(row['complex_coherence_error'] for row in active),
            low20_300_change_db=low['power_delta_db'],peak_raw_FS=float(abs(mixed).max()),performance=perf))
        print(json.dumps(r['trials'][-1]),flush=True)
    # Source halves quantify within-recording drift, not holdout engine validation.
    r['reference_half_drift']=error(matrices(reference[:len(reference)//2],bands),matrices(reference[len(reference)//2:],bands))
    r['result']='stereo_candidate_technical_pass';r['limits']=[
        'One startup-settling cabin context, not confirmed warm idle or exterior transfer',
        '600..850Hz remains unfilled; positive-debt detail cannot repair an indefinite covariance difference',
        'Stationary new excitation; no validated cycle envelope, acceleration/load axis or physical source separation',
        'No native/device/take/driver/physical7.1.4 or listening acceptance; standalone block timing is diagnostic only']
except Exception as exc:r.update(result='failed',error=repr(exc));raise
finally:
    r['evidence_sha256']={v.relative_to(a.out).as_posix():sha(v) for v in a.out.rglob('*') if v.is_file() and 'exact_sources' not in v.parts}
    (a.out/'report.json').write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
