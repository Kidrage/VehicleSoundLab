"""Independent spline/motion/OSC checks for the optional C shared-phase source."""
import argparse,csv,json,shutil,subprocess,sys
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--workspace',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
a=p.parse_args();repo=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(a.workspace/'tools/python_deps'))
import numpy as np
import soundfile as sf
from scipy import signal
from scipy.interpolate import CubicSpline
from sustain_osc_v1.oracle import Gaussian
from harmonic_magnitude_v1.legacy import parse
from phase_texture_v1.render import render
from drive_evidence_v1.sources import sha
from residual_osc_v1.spectrum import matrices,error

a.out.mkdir(parents=True,exist_ok=False)
r=dict(schema='vsl.phase-texture-C-verification/1',result='running',trials=[],source_sha256={},
       offline_light_accepted=True,native_listening_accepted=False,source_phase_calibrated=False)
try:
    paths=[repo/'handoff/CMakeLists.txt',repo/'modules/dna_scene/CMakeLists.txt',Path(__file__)]
    for folder in ('src','modules','experiments','tests'):
        paths.extend(x for x in (repo/folder).rglob('*') if x.suffix in ('.c','.h') or x.name=='CMakeLists.txt')
    for path in paths:
        name=path.relative_to(repo).as_posix();target=a.out/'exact_sources'/name
        target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(path,target);r['source_sha256'][name]=sha(path)
    accepted=json.loads((repo/'research/coherent_low_v1_acceptance.json').read_text(encoding='utf-8'))
    dna=repo/'voices/dna_bank_v1/V10 Exterior.model';low=repo/accepted['model']
    assert sha(dna)==accepted['dna_model_sha256'] and sha(low)==accepted['model_sha256']
    r['model_sha256']={str(x.relative_to(repo)):sha(x) for x in (dna,low)}
    exe=repo/'build-phase-texture-c-v1/Release/VslPhaseTexture_probe.exe'
    assert exe.exists();r['probe_sha256']=sha(exe)
    frames=384000;model=parse(dna);hz=np.arange(1,len(model['mean'])+1)*46.875
    u=np.clip((hz-1200)/700,0,1);mask=.5-.5*np.cos(np.pi*u)
    frozen_dna,rate=sf.read(a.workspace/'baselines/coherent_low_v1/evidence/raw/dna.wav',dtype='float32',always_2d=True)
    frozen_low,rate2=sf.read(a.workspace/'baselines/coherent_low_v1/evidence/raw/measured.wav',dtype='float32',always_2d=True)
    assert rate==rate2==48000
    first_motion=None
    for seed in (8121907,23117,61927):
        for amount in ((0,1) if seed==8121907 else (1,)):
            out=a.out/f'seed_{seed}_amount_{amount}';out.mkdir()
            done=subprocess.run([str(exe),str(dna),str(low),str(amount),'1','8',str(seed),str(out)],capture_output=True,timeout=60)
            (out/'probe.log').write_bytes(done.stdout+done.stderr);assert done.returncode==0
            motion=np.fromfile(out/'motion.f64',dtype='<f8');assert motion.shape==(frames,)
            # Reproduce only the independent innovations, then use SciPy's
            # full-length filter and global spline, never C's piecewise solver.
            rng=Gaussian(seed);count=(frames+255)//256+100
            noise=np.array([rng.next() for _ in range(count+2048)])
            sos=signal.butter(2,[20,70],fs=187.5,btype='bandpass',output='sos')
            impulse=np.zeros(2048);impulse[0]=1
            nodes=signal.sosfilt(sos,noise)[2048:]/np.sqrt(np.sum(signal.sosfilt(sos,impulse)**2))
            expected=4e-6*np.tanh(CubicSpline(np.arange(count)*256,nodes,bc_type='natural')(np.arange(frames))/2)
            motion_error=float(np.max(abs(motion-expected)));assert motion_error<2e-14
            x,rate=sf.read(out/'dna.wav',dtype='float32',always_2d=True)
            lf,rate2=sf.read(out/'low.wav',dtype='float32',always_2d=True)
            assert rate==rate2==48000 and np.array_equal(lf,frozen_low[:frames])
            original,delta=render(model,frames,48271,motion*amount,mask)
            oracle_error=float(np.max(abs(x.astype(float)-(original+delta))));assert oracle_error<2e-7
            if amount==0:assert np.array_equal(x,frozen_dna[:frames])
            else:
                if first_motion is None:first_motion=motion.copy()
                power=error(matrices(frozen_dna[24000:frames]),matrices(x[24000:frames]))
                max_power=max(abs(v) for row in power for v in row['power_delta_db']);assert max_power<.02
                freq,psd=signal.welch(motion[24000:],fs=48000,nperseg=48000)
                slow=float(psd[freq<4].sum()/psd.sum());assert slow<.001
            row=dict(seed=seed,amount=amount,motion_vs_global_scipy_error_seconds=motion_error,
                independent_direct_OSC_error_FS=oracle_error,bypass_float_exact=amount==0,LF_float_exact=True,
                motion_RMS_us=float(np.sqrt(np.mean(motion[24000:]**2))*1e6),
                motion_bound_us=float(np.max(abs(motion))*1e6),files={p.name:sha(p) for p in out.iterdir()})
            if amount:row.update(maximum_band_power_change_db=max_power,motion_below4Hz_power_fraction=slow)
            r['trials'].append(row);print(json.dumps({k:v for k,v in row.items() if k!='files'}),flush=True)
    # Two bounded pitch cases test the actual C host and independent LF identity
    # at the same pitch; they are new listening candidates, not accepted data.
    for pitch in (.9,1.1):
        outputs=[]
        for amount in (0,1):
            out=a.out/f'pitch_{pitch}_amount_{amount}';out.mkdir()
            done=subprocess.run([str(exe),str(dna),str(low),str(amount),str(pitch),'4','8121907',str(out)],capture_output=True,timeout=60)
            assert done.returncode==0;outputs.append(out)
        x=sf.read(outputs[0]/'low.wav',dtype='float32')[0];y=sf.read(outputs[1]/'low.wav',dtype='float32')[0]
        assert np.array_equal(x,y)
    r.update(result='pass',independent_global_spline_and_OSC_checked=True,
        original_sound_dna_C_unchanged=True,LF_unchanged=True,
        motion_RNG='independent xorshift64star/BoxMuller; original offline candidate used NumPy PCG64',
        native_waveform_equal_to_accepted_offline=False,
        limits=['Same stochastic filter/spline/scale, new innovation sequence; native listening still required',
                'No measured engine-jitter calibration, full states or new multichannel spatial evidence'])
except Exception as exc:r.update(result='failed',error=repr(exc));raise
finally:(a.out/'report.json').write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
print(json.dumps(dict(result=r['result'],trials=len(r['trials']))))
