"""Independent numerical checks, signal-level audit and evidence freeze."""
import csv
import json
import shutil
from dataclasses import replace
from runtime_review import ROOT, sha
from reference_segments import checked_source
from envelope_cycles import EnvelopeSettings, analytic_filter, band_analytic, score
import numpy as np
from scipy import signal

OUT=ROOT/'references/analysis/envelope_cycles_detrended_v1'
INITIAL=ROOT/'references/analysis/envelope_cycles_v1'
SNAP=ROOT/'baselines/envelope_cycles_v1'


def read(path):return json.loads(path.read_text(encoding='utf-8'))


def independent_checks():
    rng=np.random.default_rng(48271);n,bins=64,128
    power=np.exp(.3*rng.normal(size=(n,bins,2)))
    inverse=(np.arange(n)[:,None]+np.arange(bins)[None,:]/bins)*.05
    settings=EnvelopeSettings();result=score(power,inverse,8,settings)
    shape=power/power.mean(axis=1,keepdims=True)-1
    phase=2*np.pi*np.arange(bins)/bins
    basis=np.column_stack([np.cos(k*phase) for k in range(1,9)]+[np.sin(k*phase) for k in range(1,9)])
    actual=np.zeros(2);error=np.zeros(2);floor=np.zeros(2)
    for fold in result['folds']:
        a,b=fold['train_cycles'];c,d=fold['test_cycles']
        # Direct trigonometric least squares and actual time-domain residuals
        # are independent of the scorer's FFT/Parseval cross-product formula.
        template=basis@np.linalg.lstsq(basis,shape[a:b].mean(axis=0),rcond=None)[0]
        test=shape[c:d]
        prediction=basis@np.linalg.lstsq(basis,test.transpose(1,0,2).reshape(bins,-1),rcond=None)[0]
        prediction=prediction.reshape(bins,d-c,2).transpose(1,0,2)
        actual+=(test*test).sum(axis=(0,1))
        error+=((test-template)**2).sum(axis=(0,1))
        floor+=((test-prediction)**2).sum(axis=(0,1))
    direct_error=10*np.log10(error/actual);direct_floor=10*np.log10(floor/actual)
    assert np.max(abs(direct_error-result['future_envelope_error_db_lr']))<1e-12
    assert np.max(abs(direct_floor-result['per_test_cycle_harmonic_projection_floor_db_lr']))<1e-12
    scaled=score(power*np.array([.03,17.]),inverse,8,settings)
    swapped=score(power[:,:,::-1],inverse,8,settings)
    rotated=score(np.roll(power,17,axis=1),inverse,8,settings)
    for key in ['future_envelope_error_db_lr','phase_contrast_db_lr']:
        assert np.max(abs(np.array(scaled[key])-result[key]))<1e-12
        assert np.max(abs(np.array(swapped[key])[::-1]-result[key]))<1e-12
        assert np.max(abs(np.array(rotated[key])-result[key]))<1e-12
    # Analytic cosine: random fractional phase shifts have exact relative
    # error2-2cos(delta), averaged over held-out cycles. No FFT needed here.
    cosine=np.broadcast_to((1+.7*np.cos(phase))[None,:,None],(n,bins,2)).copy()
    contrast=score(cosine,inverse,8,settings);closed=np.zeros(64);count=0
    rng=np.random.default_rng(48271)
    for fold in contrast['folds']:
        length=fold['test_cycles'][1]-fold['test_cycles'][0]
        offsets=rng.uniform(0,1,(64,length));closed+=(2-2*np.cos(2*np.pi*offsets)).sum(axis=1);count+=length
    closed_quantiles=np.percentile(10*np.log10(closed/count),[5,50,95])
    assert np.max(abs(np.array(contrast['phase_shift_error_db_p05_median_p95_lr'])-closed_quantiles[:,None]))<1e-12
    # Independent direct convolution checks both analytic channels.
    x=rng.normal(0,.1,(4096,2));h=analytic_filter(48000,(3000,8000),settings)
    fft=band_analytic(x,48000,(3000,8000),settings)
    direct=np.column_stack([signal.convolve(x[:,c],h,mode='same',method='direct') for c in range(2)])
    maximum=float(np.max(abs(fft-direct)));assert maximum<1e-14
    raw_support=(settings.filter_taps-1)/48000+2*settings.trend_sigma_seconds*settings.trend_truncate+20/48000
    assert raw_support<settings.purge_seconds
    return dict(result='pass',direct_trigonometric_LS_error_db_lr=direct_error.tolist(),
        direct_trigonometric_projection_floor_db_lr=direct_floor.tolist(),
        fractional_phase_cosine_closed_form_quantiles_db=closed_quantiles.tolist(),
        direct_vs_FFT_analytic_convolution_maximum_error=maximum,
        gain_invariance=True,channel_swap=True,within_cycle_rotation_invariance=True,
        total_two_sided_finite_envelope_support_seconds=raw_support,purge_seconds=settings.purge_seconds)


def main():
    if SNAP.exists() or (OUT/'verification.json').exists():raise SystemExit('Preserve completed envelope_cycles_v1.')
    result=read(OUT/'results.json');initial=read(INITIAL/'results.json');math=independent_checks()
    assert result['initial_cycle_mean_only']['sha256']==sha(INITIAL/'results.json')
    for source in [result,initial]:
        folder=OUT if source is result else INITIAL
        for name,digest in source['files'].items():assert sha(folder/name)==digest,name
        for name,digest in source['source_files'].items():
            saved=INITIAL/'initial_sources'/name
            path=saved if source is initial and saved.exists() else ROOT/name
            assert sha(path)==digest,str(path)
        for name,digest in source['inputs'].items():assert sha(ROOT/name)==digest,name
        assert sha(ROOT/source['ridge_source']['path'])==source['ridge_source']['sha256']
    controls=result['controls']['signals']
    assert controls['smooth_fade_arbitrary_clock']['finite_log_trend_removed']['status']=='unmeasured'
    assert min(controls['smooth_fade_arbitrary_clock']['initial_cycle_mean_only']['phase_contrast_db_lr'])>14
    assert max(abs(np.array(controls['unmodulated_noise']['phase_contrast_db_lr'])))<.02
    assert min(controls['phase_modulated_noise']['phase_contrast_db_lr'])>1.6
    assert controls['analytic_AM_chirp']['analytic_envelope_error_db']<-76
    assert controls['single_tone']['status']=='unmeasured'
    measured=0;fold_count=0
    for group in ['reference','native']:
        for item in result[group].values():
            for row in item['measurements']:
                if row['status']!='measured':continue
                measured+=1;last=-1
                for fold in row['folds']:
                    assert fold['centre_gap_seconds']>=result['settings']['purge_seconds']-1e-10
                    assert fold['train_cycles'][1]<=fold['test_cycles'][0]
                    assert fold['test_cycles'][0]>=last;last=fold['test_cycles'][1];fold_count+=1
    assert measured==120
    cut=result['native']['neutral_cut']['measurements']
    assert len(cut)==8 and all(row['status']=='unmeasured' and 'Raw band below' in row['reason'] for row in cut)
    for item in result['reference'].values():
        assert item['reference']['segment_id']=='A_exterior_blips' and item['reference']['channels']==2
        assert item['reference']['master_sha256']==checked_source('A')['master_sha256']
    plots=read(OUT/'checked_plot.json')
    assert plots['plot_sha256']==sha(OUT/'envelope_cycles_checked.png')
    assert plots['primary_sha256']==sha(OUT/'results.json') and plots['script_sha256']==sha(ROOT/'tools/plot_envelope_cycles.py')
    for name,digest in plots['inputs'].items():assert sha(OUT/name)==digest
    native=read(ROOT/'renders/v0.16.0/verification.json');source_count=0
    for name,digest in native['binaries'].items():assert sha(ROOT/'build-v016/Release'/name)==digest
    for item in read(ROOT/'baselines/v0.16.0/manifest.json')['files']:
        name=item['path']
        if name.startswith(('src/','tests/')) or name in ['CMakeLists.txt','Launch.cmd','Launch-character.cmd','build.ps1','AGENTS.md']:
            assert sha(ROOT/name)==item['sha256'],name
            source_count+=1
    assert source_count==144
    media={key:checked_source(key) for key in ['A','B']}
    assert sha(ROOT/media['A']['video'])==media['A']['video_sha256']
    history={p.parent.name:sha(p) for p in sorted((ROOT/'baselines').glob('*/manifest.json'))};assert len(history)==24
    paths=['tools/envelope_cycles.py','tools/analyze_envelope_cycles.py','tools/plot_envelope_cycles.py','tools/verify_envelope_cycles.py',
        'tools/cycle_prediction.py','tools/reference_segments.py','tools/runtime_review.py','references/segments_v1.json',
        'research/高频能量与逐次节奏核查V1.md','research/goal_progress_envelope_cycles_v1.json','README.md']
    report=dict(result='pass',study='envelope_cycles_v1',runtime='0.16.0 unchanged',independent_checks=math,
        primary_sha256=sha(OUT/'results.json'),initial_sha256=sha(INITIAL/'results.json'),
        measured_combinations=measured,checked_future_folds=fold_count,
        native_source_and_contract_files_unchanged=source_count,native_binaries_unchanged=native['binaries'],
        approved_media=media,previous_snapshot_manifest_hashes=history,
        source_files={name:sha(ROOT/name) for name in paths},
        artifacts={p.relative_to(ROOT).as_posix():sha(p) for folder in [OUT,INITIAL] for p in sorted(folder.rglob('*')) if p.is_file()},
        scope='Conditional offline envelope evidence and confound correction. No new voicing, physical cylinder/noise decomposition, A/V telemetry, subjective acceptance or physical-array validation.')
    (OUT/'verification.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    paths += [p.relative_to(ROOT).as_posix() for folder in [OUT,INITIAL] for p in sorted(folder.rglob('*')) if p.is_file()]
    SNAP.mkdir()
    for name in paths:
        target=SNAP/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(ROOT/name,target)
    files=[dict(path=p.relative_to(SNAP).as_posix(),sha256=sha(p)) for p in sorted(SNAP.rglob('*')) if p.is_file()]
    (SNAP/'manifest.json').write_text(json.dumps(dict(study='envelope_cycles_v1',runtime='0.16.0 unchanged',files=files,
        native_snapshot_manifest_sha256=sha(ROOT/'baselines/v0.16.0/manifest.json'),
        status='Frozen analysis with initial cycle-mean confound and corrected finite trend study; no listening acceptance.',
        storage='Analysis tools, exact initial source copies, results, grids, plots and report. Raw media and native float outputs stay at original hash-bound paths.'),indent=2),encoding='utf-8')
    assert all(sha(SNAP/item['path'])==item['sha256'] for item in files)
    print(json.dumps(dict(result='pass',snapshot_files=len(files),measured_combinations=measured,checked_future_folds=fold_count,
        independent_checks=math,native_files_unchanged=source_count),indent=2))


if __name__=='__main__':main()
