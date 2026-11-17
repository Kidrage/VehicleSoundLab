"""Independent raw-frame FFT audit of the actual C multi-stage envelope candidate."""
import argparse
import json
from pathlib import Path
import shutil
import numpy as np
import soundfile as sf
from audit_startup_shape_v1 import powers,stats,EDGES
from event_authoring.native import Renderer
from event_authoring.temporal_fit import band_curves
from event_designer.package import write_json


def spectral_power(x):
    if x.ndim==1:x=x[:,None]
    window=.5-.5*np.cos(2*np.pi*np.arange(2048)/2048)
    frequency=np.arange(1025)*48000/2048;rows=[]
    for start in range(0,len(x)-2048+1,1024):
        z=np.fft.rfft(x[start:start+2048]*window[:,None],axis=0)
        p=(z.real*z.real+z.imag*z.imag)/(48000*np.sum(window*window));p[1:-1]*=2
        rows.append(p.mean(axis=1))
    return frequency,np.mean(rows,axis=0)


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True)
    out=parser.parse_args().output;out.mkdir(parents=True,exist_ok=False)
    repo=Path(__file__).resolve().parents[1];root=Path('E:/VehicleSoundLab/references/analysis/startup_contour_v1')
    original=json.loads(Path('E:/VehicleSoundLab/references/analysis/startup_shape_v1/candidate2/analysis/profile.json').read_text(encoding='utf-8'))
    candidate=json.loads((root/'candidate1/analysis/profile.json').read_text(encoding='utf-8'))
    with sf.SoundFile('E:/VehicleSoundLab/references/clean/A_decoded_float.wav') as stream:
        assert stream.samplerate==48000;stream.seek(1786560);raw=stream.read(38400,always_2d=True)
        stream.seek(1680000);bg=stream.read(57600,always_2d=True)
    copied,_=sf.read(root/'candidate1/analysis/reference.wav',always_2d=True);assert np.array_equal(raw,copied)
    t,recorded=powers(raw);_,background=powers(bg);target=np.maximum(recorded-background.mean(axis=1)[:,None],0)
    f,raw_psd=spectral_power(raw);_,bg_psd=spectral_power(bg)
    excess=np.maximum(raw_psd-bg_psd,0)
    spectral_target=np.array([excess[(f>=lo)&(f<hi)].sum()*48000/2048 for lo,hi in EDGES])
    # Check the fitter's observation against a separately implemented per-frame rFFT.
    ft,fp=band_curves(raw);np.testing.assert_allclose(ft,t,rtol=0,atol=1e-15)
    np.testing.assert_allclose(fp,recorded[1:5],rtol=2e-12,atol=2e-15)
    renderer=Renderer(repo);rows=[];scale=np.maximum(target.mean(axis=1),1e-15)
    for seed in (27431,48271,93931,17389):
        before,_=renderer.render(original['parameters'],'catch',dict(seconds=1.2,seed=seed))
        after,_=sf.read(root/f'verification1/{seed}/synthesis.wav')
        direct,_=renderer.render(candidate['parameters'],'catch',dict(seconds=1.2,seed=seed))
        assert np.array_equal(after,direct) and np.all(after[38400:]==0)
        sf.write(out/f'original-{seed}.wav',before,48000,subtype='FLOAT')
        _,old=powers(before[:38400]);_,new=powers(after[:38400])
        old_error=np.sqrt(np.mean(((old-target)/scale[:,None])**2,axis=1))
        new_error=np.sqrt(np.mean(((new-target)/scale[:,None])**2,axis=1))
        assert np.all(new_error[3:5]<old_error[3:5]),(seed,old_error,new_error)
        _,new_psd=spectral_power(after[:38400]);spectral=[]
        for (lo,hi),amount in zip(EDGES,spectral_target):
            generated=float(new_psd[(f>=lo)&(f<hi)].sum()*48000/2048)
            error=float(10*np.log10(max(generated,1e-30)/max(amount,1e-30)))
            significant=amount>=spectral_target.sum()*1e-4
            passed=abs(error)<=3 if significant else generated<=max(amount*2,spectral_target.sum()*2e-4)
            spectral.append(dict(hz=[lo,hi],error_db=error,passed=bool(passed)))
        assert all(r['passed'] for r in spectral),(seed,spectral)
        if seed==27431:
            np.testing.assert_allclose([r['error_db'] for r in spectral],
                [r['error_db'] for r in candidate['fit']['source_response_fit']['bands']],atol=2e-6,rtol=0)
        rows.append(dict(seed=seed,normalized_power_curve_rmse_before=old_error.tolist(),
            normalized_power_curve_rmse_after=new_error.tolist(),bands=stats(t,new),
            original_six_spectral_gates=spectral,
            mean_power_error_db=(10*np.log10(np.maximum(new.mean(axis=1),1e-30)/np.maximum(target.mean(axis=1),1e-30))).tolist(),
            peak=float(np.max(abs(after))),tail_zero=True))
    sf.write(out/'reference.wav',raw,48000,subtype='FLOAT')
    np.savez(out/'curves.npz',time=t,target=target,original=old,candidate=new)
    write_json(out/'report.json',dict(result='passed',raw_reference_exact=True,
        method='Explicit2048 periodic Hann/per-channel rFFT squared/mean channel power/240-frame hop, six bands, positive background power subtraction. Independent of contour optimizer and scipy spectrogram.',
        edges=EDGES,source_bands=stats(t,target),results=rows,observation_crosscheck_passed=True,
        all_four_C_seeds_improve_both_upper_band_curve_errors=True,
        all_four_C_seeds_pass_original_six_band_spectral_gates=True,
        limitations='Same fixed crop and coarse power curves; no mechanical timbre acceptance or physical RPM/source separation. Lower bands can change because all component amplitudes are recalibrated. No claim of reconstructing all high-frequency fine structure.'))
    shutil.copy2(__file__,out/'executed_audit.py')
    print(json.dumps(dict(result='passed',results=rows)),flush=True)


if __name__=='__main__':main()
