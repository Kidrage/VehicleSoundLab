"""Independent FFT and multi-seed audit of the two fixed joint-fit trials."""
import argparse
from pathlib import Path
import shutil
import numpy as np
import soundfile as sf
from audit_startup_shape_v1 import powers,EDGES
from audit_startup_contour_v1 import spectral_power
from event_authoring.audio import read
from event_authoring.native import Renderer
from event_authoring.temporal_fit import band_curves
from research_archive_v1 import load,save
from author_event import author


def shape_error(power,target):
    normalized=power/np.maximum(power.mean(axis=1),1e-30)[:,None]
    reference=target/np.maximum(target.mean(axis=1),1e-30)[:,None]
    return np.sqrt(np.mean((normalized-reference)**2,axis=1))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    out=parser.parse_args().output;out.mkdir(parents=True,exist_ok=False)
    repo=Path(__file__).resolve().parents[1];root=Path('E:/VehicleSoundLab/references/analysis')
    renderer=Renderer(repo);cases=[]
    for key,oldpath in [('A',root/'startup_contour_v1/candidate1/analysis/profile.json'),
                        ('B',root/'B_startup_context_v1/crank-hold-author1/profile.json')]:
        folder=out/key;folder.mkdir()
        candidate=load(root/'event_joint_v1/verification2'/key/'analysis/profile.json')
        old=load(oldpath);job=candidate['source_job'];duration=job['seconds'][1]-job['seconds'][0]
        # The joint fitter's nonregression gate compares against its own entry
        # (band-attack + spectral search), not a separately published contour.
        # Audit both; preserve any tradeoff against that published candidate.
        entry_job=dict(job,envelope_fit='band-attack-v1')
        save(folder/'entry.job.json',entry_job);author(folder/'entry.job.json',folder/'entry')
        entry=load(folder/'entry/profile.json')
        raw,_,source=read(Path(job['source']),*job['seconds'])
        bg,_,background=read(Path(job['source']),*job['background_seconds'])
        # A's job uses a cropped context WAV. Cross-check both materials all the
        # way back to the decoded approved master, using exact sample offsets.
        first,last,bgfirst,bglast=(1786560,1824960,1680000,1737600) if key=='A' else (729600,765600,585600,633600)
        master=Path(f'E:/VehicleSoundLab/references/clean/{key}_decoded_float.wav')
        with sf.SoundFile(master) as stream:
            assert stream.samplerate==48000;stream.seek(first);original_raw=stream.read(last-first,always_2d=True)
            stream.seek(bgfirst);original_bg=stream.read(bglast-bgfirst,always_2d=True)
        assert np.array_equal(raw,original_raw) and np.array_equal(bg,original_bg)
        copied,_=sf.read(root/'event_joint_v1/verification2'/key/'analysis/reference.wav',always_2d=True)
        assert np.array_equal(raw,copied)
        t,recorded=powers(raw);_,noise=powers(bg)
        temporal=np.maximum(recorded-noise.mean(axis=1)[:,None],0)
        contrast=10*np.log10(np.maximum(recorded.mean(axis=1),1e-30)/np.maximum(noise.mean(axis=1),1e-30))
        selected=[k for k in (3,4) if contrast[k]>=3]
        declared=candidate['fit']['contour_fit']['bands']
        np.testing.assert_allclose([r['contrast_db'] for r in declared],contrast[3:5],rtol=0,atol=2e-6)
        assert selected==[k+3 for k,r in enumerate(declared) if r['selected']]
        ct,curves=band_curves(raw)
        np.testing.assert_allclose(ct,t,rtol=0,atol=1e-15)
        np.testing.assert_allclose(curves,recorded[1:5],rtol=2e-12,atol=2e-15)
        frequency,raw_psd=spectral_power(raw);_,bg_psd=spectral_power(bg)
        excess=np.maximum(raw_psd-bg_psd,0)
        spectral_target=np.array([excess[(frequency>=lo)&(frequency<hi)].sum()*48000/2048 for lo,hi in EDGES])
        seeds=[]
        for seed in (27431,48271,93931,17389):
            controls=dict(seconds=1.2,hold_seconds=duration,seed=seed)
            before,_=renderer.render(old['parameters'],job['kind'],controls)
            initial,_=renderer.render(entry['parameters'],job['kind'],controls)
            after,_=sf.read(root/f'event_joint_v1/verification2/{key}/C-{seed}.wav')
            direct,_=renderer.render(candidate['parameters'],job['kind'],controls)
            assert np.array_equal(after,direct)
            sf.write(folder/f'original-{seed}.wav',before,48000,subtype='FLOAT')
            n=len(raw);_,oldpower=powers(before[:n]);_,newpower=powers(after[:n]);_,initialpower=powers(initial[:n])
            oldshape=shape_error(oldpower,temporal);newshape=shape_error(newpower,temporal);initialshape=shape_error(initialpower,temporal)
            _,psd=spectral_power(after[:n]);gates=[]
            for (lo,hi),target in zip(EDGES,spectral_target):
                generated=float(psd[(frequency>=lo)&(frequency<hi)].sum()*48000/2048)
                error=float(10*np.log10(max(generated,1e-30)/max(target,1e-30)))
                significant=target>=spectral_target.sum()*1e-4
                passed=abs(error)<=3 if significant else generated<=max(target*2,spectral_target.sum()*2e-4)
                gates.append(dict(hz=[lo,hi],error_db=error,passed=bool(passed)))
            if seed==27431:
                np.testing.assert_allclose([g['error_db'] for g in gates],
                    [g['error_db'] for g in candidate['fit']['source_response_fit']['bands']],rtol=0,atol=2e-6)
            assert all(g['passed'] for g in gates),(key,seed,gates)
            # Temporal shape is normalized separately from the positive-bin PSD target.
            # Record absolute energy mismatch as well; never call those targets equal.
            energy_error=10*np.log10(np.maximum(newpower.mean(axis=1),1e-30)/np.maximum(temporal.mean(axis=1),1e-30))
            if seed==27431:np.testing.assert_allclose(initialshape[selected],candidate['fit']['contour_fit']['baseline_shape_rmse'],rtol=0,atol=2e-6)
            assert np.all(newshape[selected]<initialshape[selected]),(key,seed,initialshape,newshape)
            if not candidate['parameters']['gated']:assert not np.any(after[n:])
            seeds.append(dict(seed=seed,original_six_spectral_gates=gates,
                shape_rmse_before=oldshape.tolist(),shape_rmse_after=newshape.tolist(),
                shape_rmse_entry=initialshape.tolist(),
                versus_published_candidate_improves_selected=(newshape[selected]<oldshape[selected]).tolist(),
                absolute_temporal_mean_error_db=energy_error.tolist(),peak=float(np.max(abs(after)))))
            if seed==27431:np.savez(folder/'curves.npz',time=t,recorded=recorded,background=noise,
                target=temporal,original=oldpower,candidate=newpower,contrast_db=contrast)
        cases.append(dict(key=key,source=source,background=background,contrast_db=contrast.tolist(),
            approved_master=str(master),master_event_frames=[first,last],master_background_frames=[bgfirst,bglast],
            selected_band_indices=selected,spectral_to_temporal_target_ratio=(spectral_target/np.maximum(temporal.mean(axis=1),1e-30)).tolist(),
            seeds=seeds,raw_reference_exact=True))
    save(out/'report.json',dict(result='passed',cases=cases,author_bridge_sha256=renderer.identity,
        method='Explicit periodic2048 Hann/per-channel rFFT/channel-power mean. Temporal hop240 and positive band-total background subtraction; spectral hop1024 and positive per-bin background subtraction. Original six spectral gates unchanged. Four actual C seeds per material.',
        limitations='Two fixed same-material trials; normalized curve improvement does not prove mechanical timbre, independent engine source separation, physical RPM, held-out generality or complete high-frequency detail.',timbre_accepted=False))
    shutil.copy2(__file__,out/'executed_audit.py')
    print(dict(result='passed',materials=2,C_seeds=8),flush=True)


if __name__=='__main__':main()
