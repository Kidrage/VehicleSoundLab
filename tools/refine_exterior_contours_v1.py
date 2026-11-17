"""One predeclared gain-only solve for each existing exterior-start profile."""
import argparse
from copy import deepcopy
from pathlib import Path
import shutil

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import soundfile as sf

from event_authoring.audio import read
from event_authoring.measure import observe
from event_authoring.contour_all_bands import observations
from event_authoring.contour_ensemble import solve, validate_candidate, gains, TEMPORAL_EDGES
from event_authoring.response_ensemble import TRAIN_SEEDS, HELD_OUT_SEEDS, target_powers, band_powers
from event_authoring.response_fit import EDGES
from event_authoring.temporal_fit import band_curves
from event_authoring.native import Renderer, controls
from event_authoring.model import synth
from research_archive_v1 import load, save, sha


def native_assess(wave, targets, reference, indices, baseline):
    power = band_powers(wave.astype(float))
    total = float(targets.sum())
    spectral = []
    for edge, target, actual in zip(EDGES, targets, power):
        db = float(10*np.log10(max(actual, 1e-30)/max(target, 1e-30)))
        passed = abs(db) <= 3 if target >= total*1e-4 else actual <= max(2*target, total*2e-4)
        spectral.append(dict(hz=list(edge), error_db=db, target_power=float(target),
                             generated_power=float(actual), passed=bool(passed)))
    _, curve = band_curves(wave.astype(float))
    normalized = curve/np.maximum(curve.mean(axis=1), 1e-30)[:, None]
    errors = np.sqrt(np.mean((normalized-reference)**2, axis=1))
    temporal = baseline is None or all(errors[i] <= baseline[i]+1e-10 for i in indices)
    return dict(bands=spectral, shape_rmse=errors.tolist(), temporal_nonregression=bool(temporal),
                qualified=bool(temporal and all(row['passed'] for row in spectral))), normalized


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    out = parser.parse_args().output
    out.mkdir(parents=True, exist_ok=False)
    repo = Path(__file__).resolve().parents[1]
    root = Path('E:/VehicleSoundLab/references/analysis')
    probe = root/'startup_contour_ensemble_v1/known1'
    assert load(probe/'report.json')['result'] == 'passed'
    assert sha(repo/'tools/event_authoring/contour_ensemble.py') == sha(
        probe/'exact_sources/tools/event_authoring/contour_ensemble.py')
    baseline_path = root/'startup_contour_ensemble_v1/baseline1/report.json'
    baseline = load(baseline_path)
    assert baseline['result'] == 'passed'
    for path in [Path(__file__), repo/'research/startup_contour_ensemble_v1_plan.json',
                 *sorted((repo/'tools/event_authoring').glob('*.py'))]:
        destination = out/'exact_sources'/path.relative_to(repo)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, destination)
    renderer = Renderer(repo)
    report = dict(result='running', known_first_report=str(probe/'report.json'),
        known_first_report_sha256=sha(probe/'report.json'), baseline_report=str(baseline_path),
        baseline_report_sha256=sha(baseline_path), goal_complete=False, timbre_accepted=False,
        runtime_optimized=False, new_spatial_processing=False, cases=[])
    save(out/'report.json', report)
    fig, axes = plt.subplots(4, 2, figsize=(12, 11), layout='constrained')
    for column, entry in enumerate(baseline['cases']):
        kind = entry['kind']
        folder = out/kind
        folder.mkdir()
        document_path = Path(entry['document'])
        assert sha(document_path) == entry['document_sha256']
        original = load(document_path)
        job = original['source_job']
        x, rate, source = read(job['source'], *job['seconds'])
        bg, _, background = read(job['source'], *job['background_seconds'])
        assert source == entry['source'] and background == entry['background']
        assert len(x) == entry['observation_frames']
        duration = len(x)/rate
        _, arrays = observe(x, bg)
        targets = target_powers(arrays)
        time, target, bands = observations(x, bg)
        reference = target/np.maximum(target.mean(axis=1), 1e-30)[:, None]
        indices = [i for i, row in enumerate(bands) if row['selected']]
        print(kind, 'one training solve begins', flush=True)
        candidate, fitting = solve(original['parameters'], target, bands, targets, duration)
        # Persist the sole solution before any held-out or actual-C candidate evaluation.
        candidate_path = folder/'candidate-parameters-before-validation.json'
        save(candidate_path, candidate)
        save(folder/'training-report-before-validation.json', fitting)
        fixed_sha = sha(candidate_path)
        fitting = validate_candidate(original['parameters'], candidate, target, bands, targets, duration, fitting)
        assert sha(candidate_path) == fixed_sha
        save(folder/'fit-report.json', fitting)
        print(kind, 'fixed candidate validation', fitting['qualified'],
              fitting['relative_improvement'], flush=True)
        native_rows, old_curves, new_curves = [], [], []
        for seed in (*TRAIN_SEEDS, *HELD_OUT_SEEDS):
            row = dict(seed=seed)
            for label, parameters in [('old', original['parameters']), ('candidate', candidate)]:
                wave, native = renderer.render(parameters, kind, controls(dict(
                    seed=seed, seconds=duration+.15, hold_seconds=duration)))
                expected = synth(parameters, seed=seed, seconds=len(wave)/rate,
                                 release_at=duration if parameters['gated'] else None)
                expected = np.pad(expected, (0, len(wave)-len(expected)))
                error = float(np.max(abs(wave-expected)))
                assert error < 2e-6
                sf.write(folder/(label+'-'+str(seed)+'.wav'), wave, rate, subtype='FLOAT')
                assessed, curve = native_assess(wave[:len(x)], targets, reference, indices,
                    None if label == 'old' else row['old']['shape_rmse'])
                assessed.update(C_python_max_error_FS=error, peak=float(np.max(abs(wave))))
                row[label] = assessed
                (old_curves if label == 'old' else new_curves).append(curve)
            native_rows.append(row)
        c_qualified = all(row['candidate']['qualified'] for row in native_rows)
        eligible = bool(fitting['qualified'] and c_qualified)
        # Even eligible results remain opt-in candidates; never overwrite the original project.
        candidate_doc = deepcopy(original)
        candidate_doc['parameters'] = candidate
        candidate_doc['contour_refinement'] = dict(method='existing-contour-ensemble-v1',
            original_document=str(document_path), original_sha256=entry['document_sha256'],
            candidate_sha256=fixed_sha, eligible=eligible, accepted=False)
        save(folder/'candidate-event-profile.json', candidate_doc)
        save(folder/'original-event-profile.json', original)
        for band, edge in enumerate(TEMPORAL_EDGES):
            ax = axes[band, column]
            ax.plot(time, reference[band], color='black', lw=1.3, label='material excess')
            for name, curves, color in [('old', old_curves, '#b25937'), ('candidate', new_curves, '#287598')]:
                curves = np.array(curves)[:, band]
                ax.fill_between(time, curves.min(axis=0), curves.max(axis=0), color=color, alpha=.15)
                ax.plot(time, curves.mean(axis=0), color=color, lw=1, label=name)
            ax.set_title(kind+' / '+str(edge[0])+'-'+str(edge[1])+' Hz')
            ax.set_xlabel('seconds within fixed crop')
            ax.set_ylabel('mean-normalized power')
            if band == 0:
                ax.legend(fontsize=8)
        report['cases'].append(dict(kind=kind, document=str(document_path),
            document_sha256=entry['document_sha256'], source=source, background=background,
            observation_frames=len(x), bands=bands, candidate_parameters_sha256=fixed_sha,
            fitting=fitting, native=native_rows, all_native_checks_pass=c_qualified,
            eligible_for_optional_authoring=eligible, adopted=False,
            initial_gains=gains(original['parameters']).tolist(), candidate_gains=gains(candidate).tolist()))
        save(out/'report.json', report)
    fig.savefig(out/'temporal.png', dpi=160)
    plt.close(fig)
    bindings = load(root/'A_exterior_startup_v1/selection1/runtime.json')
    assert len(bindings) == 459 and all(sha(repo/name) == digest for name, digest in bindings.items())
    report.update(result='passed', runtime_voice_files_unchanged=459,
                  actual_renderer_sha256=renderer.identity,
                  qualified_cases=[c['kind'] for c in report['cases'] if c['eligible_for_optional_authoring']])
    save(out/'report.json', report)
    print('completed one solve per case; no promotion;', report['qualified_cases'], flush=True)


if __name__ == '__main__':
    main()
