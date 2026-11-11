"""Independent PSD/control checks and immutable conditional-spectrum snapshot."""
import json
import shutil
from pathlib import Path
from runtime_review import ROOT, sha
from reference_segments import checked_source
from spectral_coordinates import hat_basis
import numpy as np
import soundfile as sf
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

OUT = ROOT/'references/analysis/spectral_coordinates_log_v1'
INITIAL = ROOT/'references/analysis/spectral_coordinates_v1'
SNAP = ROOT/'baselines/spectral_coordinates_v1'


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def manual_band_power(path, seconds):
    audio, rate = sf.read(path, always_2d=True)
    audio = audio[round(seconds[0]*rate):round(seconds[1]*rate)]
    n = 4096
    window = .5-.5*np.cos(2*np.pi*np.arange(n)/n)
    spectra = []
    for first in range(0, len(audio)-n+1, n//2):
        frame = audio[first:first+n]
        frame = frame-frame.mean(axis=0)
        spectrum = abs(np.fft.rfft(frame*window[:, None], axis=0))**2/(rate*np.sum(window**2))
        spectrum[1:-1] *= 2
        spectra.append(spectrum)
    hz = np.fft.rfftfreq(n, 1/rate)
    power = np.mean(spectra, axis=0)[(hz >= 1500) & (hz < 8000)].sum(axis=0)*rate/n
    return 10*np.log10(np.maximum(power, 1e-30))


def independent_checks(primary, extension):
    # Analytic interpolation and partition of unity, independently of the fit.
    knots = np.linspace(-2, 4, 37)
    x = np.linspace(-1.9, 3.9, 127)
    weights, valid = hat_basis(x, knots)
    assert valid.all() and np.max(abs(weights.sum(axis=-1)-1)) < 1e-12
    assert np.max(abs(weights@(3*knots-7)-(3*x-7))) < 1e-12
    assert not hat_basis(np.array([-3., 5.]), knots)[1].any()
    folds = 0
    for cases in [primary['references'], primary['native'], extension['fired_shape']]:
        for row in cases.values():
            test_indices = []
            for fold in row['folds']:
                train, test = fold['train_indices'], fold['test_indices']
                assert max(train) < min(test)
                assert fold['centre_gap_seconds'] >= .192-1e-10
                assert len(test) == 10 and not set(test_indices).intersection(test)
                test_indices += test
                assert set(fold['squared_error_sum']) == {'fixed', 'moving', 'combined'}
                assert all(count >= 20 for count in fold['common_bin_counts'])
                folds += 1
    paths = {'mix': ['neutral_base.wav'],
             'exhaust': ['neutral_base_source_exhaust_left.wav', 'neutral_base_source_exhaust_right.wav'],
             'air': ['neutral_base_source_air_left.wav', 'neutral_base_source_air_right.wav']}
    differences = {}
    for group, files in paths.items():
        for state, row in extension['raw_source_levels'][group].items():
            actual = np.concatenate([manual_band_power(ROOT/'renders/exhaust_phase_v1'/name, row['seconds']) for name in files])
            error = float(np.max(abs(actual-row['raw_1500_8000_power_dbfs_lr'])))
            assert error < 1e-8, (group, state, error)
            differences[f'{group}_{state}'] = error
    # Recompute the problematic Gaussian tail using an explicit normalized
    # kernel and dot products, independent of scipy.ndimage filtering.
    grid = np.arange(-48, 49)
    kernel = np.exp(-.5*(grid/12)**2)
    kernel /= kernel.sum()
    powers = np.full((2, 240), 1e-16)
    powers[0, 45] = .01
    powers[1, 55] = .01
    sample = powers[:, 100+grid]
    linear = 10*np.log10(sample@kernel)
    logarithmic = 10*np.log10(sample)@kernel
    control = extension['known_low_tone_smoothing_control']
    assert abs(abs(float(np.diff(linear)[0]))-control['linear_power_change_db']) < 1e-10
    assert abs(abs(float(np.diff(logarithmic)[0]))-control['log_power_change_db']) < 1e-10
    return dict(result='pass', future_folds_inspected=folds,
                independent_numpy_PSD_maximum_db_difference=differences,
                interpolation_affine_and_support_checks=True,
                gaussian_tail_independent_dot_product=True)


def corrected_plot(extension):
    colors = {'fixed': '#1f77b4', 'moving': '#ff7f0e', 'combined': '#2ca02c'}
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.8), constrained_layout=True)
    for c, ax in enumerate(axes):
        for j, method in enumerate(colors):
            values = [extension['fired_shape'][name+'_smooth0.125']['spectral_shape_rmse_db_lr'][method][c]
                      for name in ['mix', 'exhaust', 'air']]
            ax.bar(np.arange(3)+(j-1)*.23, values, width=.23, label=method, color=colors[method])
        ax.set(xticks=range(3), xticklabels=['Full mix', 'Exhaust objects', 'Air objects'],
               ylabel='Held-out spectral-shape RMSE / dB',
               title=f'C FIRE / channel or object {"LR"[c]} / 3.0-4.2 s')
        ax.legend();ax.grid(axis='y', alpha=.2)
    fig.suptitle('Unmatched engineering source context / geometric PSD shape / no realism score')
    fig.savefig(OUT/'fired_shape_prediction_checked.png', dpi=160);plt.close(fig)


def main():
    if (OUT/'verification.json').exists() or SNAP.exists():
        raise SystemExit('Preserve completed spectral_coordinates_v1 snapshot.')
    primary = read(OUT/'results.json')
    extension = read(OUT/'fired_extension.json')
    for name, digest in primary['files'].items():
        assert sha(OUT/name) == digest, name
    for name, digest in primary['inputs'].items():
        assert sha(ROOT/name) == digest, name
    for name, digest in primary['tool_hashes'].items():
        assert sha(ROOT/name) == digest, name
    assert sha(ROOT/primary['reference_tracks']['path']) == primary['reference_tracks']['sha256']
    assert extension['primary_results_sha256'] == sha(OUT/'results.json')
    assert extension['source_sha256'] == sha(ROOT/'tools/analyze_fired_shape_extension.py')
    assert extension['figure_sha256'] == sha(OUT/'fired_shape_prediction.png')
    initial = read(INITIAL/'results.json')
    assert primary['initial_linear_power_study']['sha256'] == sha(INITIAL/'results.json')
    for name, digest in initial['files'].items():
        assert sha(INITIAL/name) == digest, name
    for name, digest in initial['tool_hashes'].items():
        assert sha(INITIAL/'initial_sources'/name) == digest, name
    numerical = independent_checks(primary, extension)
    corrected_plot(extension)
    native = read(ROOT/'renders/v0.16.0/verification.json')
    for name, digest in native['binaries'].items():
        assert sha(ROOT/'build-v016/Release'/name) == digest, name
    frozen = read(ROOT/'baselines/v0.16.0/manifest.json')
    source_count = 0
    for item in frozen['files']:
        name = item['path']
        if name.startswith(('src/', 'tests/')) or name in [
                'CMakeLists.txt', 'Launch.cmd', 'Launch-character.cmd', 'build.ps1', 'AGENTS.md']:
            assert sha(ROOT/name) == item['sha256'], name
            source_count += 1
    history = {}
    for folder in sorted((ROOT/'baselines').iterdir()):
        if not (folder/'manifest.json').exists():
            continue
        manifest = read(folder/'manifest.json')
        for item in manifest['files']:
            assert sha(folder/item['path']) == item['sha256'], str(folder/item['path'])
        history[folder.name] = len(manifest['files'])
    assert len(history) == 21 and history['exhaust_phase_v1'] == 91, history
    upstream = ROOT/'research/upstream/gen/v10_powertrain.gendsp'
    upstream_manifest = read(ROOT/'research/upstream_snapshot.json')
    assert sha(upstream) == next(row['sha256'] for row in upstream_manifest['files'] if row['path'] == 'gen/v10_powertrain.gendsp')
    media = {name: checked_source(name) for name in ['A', 'B']}
    paths = ['tools/spectral_coordinates.py', 'tools/analyze_spectral_coordinates.py',
             'tools/analyze_fired_shape_extension.py', 'tools/verify_spectral_coordinates.py',
             'tools/runtime_review.py', 'tools/reference_segments.py', 'references/segments_v1.json',
             'research/主排气谱包络坐标核查V1.md', 'research/goal_progress_spectral_coordinates_v1.json',
             'research/upstream/gen/v10_powertrain.gendsp', 'research/upstream_snapshot.json', 'README.md']
    report = dict(result='pass', study='spectral_coordinates_log_v1', independent_checks=numerical,
                  primary_results_sha256=sha(OUT/'results.json'), fired_extension_sha256=sha(OUT/'fired_extension.json'),
                  initial_results_sha256=sha(INITIAL/'results.json'),
                  native_source_and_contract_files_unchanged=source_count,
                  native_binaries_unchanged=native['binaries'], preserved_snapshots=history,
                  approved_media=media, pinned_upstream_sha256=sha(upstream),
                  source_files={name: sha(ROOT/name) for name in paths},
                  artifacts={p.name: sha(p) for p in sorted(OUT.iterdir()) if p.is_file()},
                  interpretation='Conditional magnitude-shape investigation only; no physical source/transfer/RPM identification or subjective acceptance. FIRE/CUT separated; initial linear-power limitation preserved. Full goal active.')
    (OUT/'verification.json').write_text(json.dumps(report, indent=2, allow_nan=False), encoding='utf-8')
    SNAP.mkdir()
    for name in paths:
        target = SNAP/name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT/name, target)
    for folder in [OUT, INITIAL]:
        files = [p for p in folder.iterdir() if p.is_file() and p.name != 'native_smoothing_diagnostic.png']
        files += list((folder/'initial_sources').rglob('*.py')) if (folder/'initial_sources').exists() else []
        for path in files:
            target = SNAP/path.relative_to(ROOT)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, target)
    files = [dict(path=str(p.relative_to(SNAP)).replace('\\', '/'), sha256=sha(p))
             for p in sorted(SNAP.rglob('*')) if p.is_file()]
    manifest = dict(study='spectral_coordinates_log_v1', runtime='0.16.0 unchanged', files=files,
                    status='Frozen conditional envelope evidence including rejected initial smoothing interpretation. No new runtime recipe or realism acceptance.')
    (SNAP/'manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    for item in files:
        assert sha(SNAP/item['path']) == item['sha256'], item['path']
    print(json.dumps(dict(result='pass', snapshot_files=len(files), preserved_snapshots=len(history),
                          native_source_files_unchanged=source_count, independent_checks=numerical), indent=2))


if __name__ == '__main__':
    main()
