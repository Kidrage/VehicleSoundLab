"""Independent raw-frame FFT audit of adaptive-knot actual C candidates."""
import argparse
from pathlib import Path
import shutil
import numpy as np
import soundfile as sf
from audit_startup_shape_v1 import powers,EDGES
from audit_startup_contour_v1 import spectral_power
from event_authoring.audio import read
from research_archive_v1 import load,save


def error(power,target):
    normalized=power/np.maximum(power.mean(axis=1),1e-30)[:,None]
    reference=target/np.maximum(target.mean(axis=1),1e-30)[:,None]
    return np.sqrt(np.mean((normalized-reference)**2,axis=1))


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True)
    out=parser.parse_args().output;out.mkdir(parents=True,exist_ok=False)
    root=Path('E:/VehicleSoundLab/references/analysis');study=root/'event_knots_v1';cases=[]
    for key,event,background in [('A',(1786560,1824960),(1680000,1737600)),('B',(729600,765600),(585600,633600))]:
        folder=out/key;folder.mkdir();doc=load(study/f'verification1/{key}/analysis/profile.json');job=doc['source_job']
        with sf.SoundFile(f'E:/VehicleSoundLab/references/clean/{key}_decoded_float.wav') as stream:
            assert stream.samplerate==48000;stream.seek(event[0]);raw=stream.read(event[1]-event[0],always_2d=True)
            stream.seek(background[0]);bg=stream.read(background[1]-background[0],always_2d=True)
        copied,_,_=read(Path(job['source']),*job['seconds']);copiedbg,_,_=read(Path(job['source']),*job['background_seconds'])
        assert np.array_equal(raw,copied) and np.array_equal(bg,copiedbg)
        reference,_=sf.read(study/f'verification1/{key}/analysis/reference.wav',always_2d=True)
        assert np.array_equal(raw,reference)
        t,recorded=powers(raw);_,noise=powers(bg);target=np.maximum(recorded-noise.mean(axis=1)[:,None],0)
        contrast=10*np.log10(np.maximum(recorded.mean(axis=1),1e-30)/np.maximum(noise.mean(axis=1),1e-30))
        selected=[k for k in (3,4) if contrast[k]>=3];fit=doc['fit']['contour_fit']
        np.testing.assert_allclose(contrast[3:5],[b['contrast_db'] for b in fit['bands']],rtol=0,atol=2e-6)
        f,psd=spectral_power(raw);_,bgpsd=spectral_power(bg);excess=np.maximum(psd-bgpsd,0)
        targets=np.array([excess[(f>=lo)&(f<hi)].sum()*48000/2048 for lo,hi in EDGES]);seeds=[]
        for seed in (27431,48271,93931,17389):
            old,_=sf.read(root/f'event_joint_v1/verification2/{key}/C-{seed}.wav')
            new,_=sf.read(study/f'verification1/{key}/C-{seed}.wav')
            _,before=powers(old[:len(raw)]);_,after=powers(new[:len(raw)]);old_error=error(before,target);new_error=error(after,target)
            if seed==27431:
                np.testing.assert_allclose(old_error[selected],fit['fixed_reference_shape_rmse'],rtol=0,atol=2e-6)
                np.testing.assert_allclose(new_error[selected],fit['attempts'][fit['selected_attempt']]['shape_rmse'],rtol=0,atol=2e-6)
            # Same declared relative-band score as candidate selection, recomputed
            # from independently transformed raw frames and actual native PCM.
            weights=1/np.maximum(np.array(fit['fixed_reference_shape_rmse']),.05)
            oldscore=float(np.mean((old_error[selected]*weights)**2));newscore=float(np.mean((new_error[selected]*weights)**2))
            assert newscore<oldscore,(key,seed,oldscore,newscore)
            _,generated=spectral_power(new[:len(raw)]);gates=[]
            for (lo,hi),amount in zip(EDGES,targets):
                actual=float(generated[(f>=lo)&(f<hi)].sum()*48000/2048)
                db=float(10*np.log10(max(actual,1e-30)/max(amount,1e-30)))
                passed=abs(db)<=3 if amount>=targets.sum()*1e-4 else actual<=max(amount*2,targets.sum()*2e-4)
                gates.append(dict(hz=[lo,hi],error_db=db,passed=bool(passed)))
            assert all(g['passed'] for g in gates),(key,seed,gates)
            if seed==27431:
                np.testing.assert_allclose([g['error_db'] for g in gates],
                    [g['error_db'] for g in doc['fit']['source_response_fit']['bands']],rtol=0,atol=2e-6)
                np.savez(folder/'curves.npz',time=t,target=target,original=before,candidate=after,contrast_db=contrast)
            if not doc['parameters']['gated']:assert not np.any(new[len(raw):])
            seeds.append(dict(seed=seed,shape_before=old_error.tolist(),shape_after=new_error.tolist(),
                relative_band_score_before=oldscore,relative_band_score_after=newscore,
                original_six_spectral_gates=gates,peak=float(np.max(abs(new)))))
        cases.append(dict(key=key,master_event_frames=event,master_background_frames=background,
            contrast_db=contrast.tolist(),selected_band_indices=selected,seeds=seeds,master_frames_exact=True))
    save(out/'report.json',dict(result='passed',cases=cases,method='Independent periodic2048 Hann/channel-mean rFFT power; temporal hop240 positive band-total subtraction, spectral hop1024 positive per-bin subtraction. Eight actual C outputs.',
        limitations='Aggregate relative-band score permits individual-band tradeoffs; not timbre acceptance, physical source/RPM identity or held-out engine generality.',timbre_accepted=False))
    shutil.copy2(__file__,out/'executed_audit.py');print(dict(result='passed',C_seeds=8),flush=True)


if __name__=='__main__':main()
