"""Execute the declared source-support candidate once per exterior profile."""
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
from event_authoring.source_support import fit_training, check_held_out, HELD_OUT_SEEDS
from event_authoring.response_ensemble import TRAIN_SEEDS, target_powers
from event_authoring.temporal_fit import band_curves
from event_authoring.native import Renderer, controls
from event_authoring.model import synth
from refine_exterior_contours_v1 import native_assess
from research_archive_v1 import load, save, sha


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    out = parser.parse_args().output
    out.mkdir(parents=True, exist_ok=False)
    repo = Path(__file__).resolve().parents[1]
    root = Path('E:/VehicleSoundLab/references/analysis')
    known = root/'startup_source_support_v1/known1'
    assert load(known/'report.json')['result'] == 'passed'
    assert sha(repo/'tools/event_authoring/source_support.py') == sha(
        known/'exact_sources/tools/event_authoring/source_support.py')
    baseline = load(root/'startup_contour_ensemble_v1/baseline1/report.json')
    for path in [Path(__file__), repo/'research/startup_source_support_v1_plan.json',
                 *sorted((repo/'tools/event_authoring').glob('*.py'))]:
        dest = out/'exact_sources'/path.relative_to(repo)
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, dest)
    renderer = Renderer(repo)
    report = dict(result='running', known_first_report=str(known/'report.json'),
        known_first_report_sha256=sha(known/'report.json'), cases=[],
        goal_complete=False, timbre_accepted=False, runtime_optimized=False, spatial_processing=False)
    save(out/'report.json', report)
    fig, axes = plt.subplots(4, 2, figsize=(12, 11), layout='constrained')
    for column, entry in enumerate(baseline['cases']):
        kind = entry['kind']
        folder = out/kind
        folder.mkdir()
        original = load(Path(entry['document']))
        assert sha(Path(entry['document'])) == entry['document_sha256']
        job = original['source_job']
        x, rate, source = read(job['source'], *job['seconds'])
        bg, _, background = read(job['source'], *job['background_seconds'])
        assert source == entry['source'] and background == entry['background']
        _, arrays = observe(x, bg)
        time, target, bands = observations(x, bg)
        reference = target/np.maximum(target.mean(axis=1), 1e-30)[:, None]
        indices = [i for i, b in enumerate(bands) if b['selected']]
        targets = target_powers(arrays)
        duration = len(x)/rate
        print(kind, 'one source-derived topology and training solve begins', flush=True)
        candidate, fitting = fit_training(original['parameters'], x, bg, arrays)
        assert candidate['modes'] == original['parameters']['modes']
        candidate_path = folder/'candidate-parameters-before-validation.json'
        save(candidate_path, candidate)
        save(folder/'training-before-validation.json', fitting)
        fixed = sha(candidate_path)
        fitting = check_held_out(original['parameters'], candidate, x, bg, arrays, fitting)
        assert sha(candidate_path) == fixed
        save(folder/'fit-report.json', fitting)
        print(kind, fitting['qualified'], fitting['relative_legacy_shape_improvement'], flush=True)
        native_rows, curves = [], {'old': [], 'candidate': []}
        for seed in (*TRAIN_SEEDS, *HELD_OUT_SEEDS):
            row = dict(seed=seed)
            for label, profile in [('old', original['parameters']), ('candidate', candidate)]:
                wave, _ = renderer.render(profile, kind, controls(dict(seed=seed,
                    seconds=duration+.15, hold_seconds=duration)))
                py = synth(profile, seed=seed, seconds=len(wave)/rate,
                           release_at=duration if profile['gated'] else None)
                py = np.pad(py, (0, len(wave)-len(py)))
                error = float(np.max(abs(wave-py)))
                assert error < 2e-6
                sf.write(folder/(label+'-'+str(seed)+'.wav'), wave, rate, subtype='FLOAT')
                measured, curve = native_assess(wave[:len(x)], targets, reference, indices,
                    None if label == 'old' else row['old']['shape_rmse'])
                measured.update(C_python_max_error_FS=error, peak=float(np.max(abs(wave))))
                row[label] = measured
                curves[label].append(curve)
            native_rows.append(row)
        eligible = bool(fitting['qualified'] and all(row['candidate']['qualified'] for row in native_rows))
        doc = deepcopy(original)
        doc['parameters'] = candidate
        doc['source_support_refinement'] = dict(method='source-support-v1',
            original_document=entry['document'], original_sha256=entry['document_sha256'],
            candidate_sha256=fixed, eligible=eligible, accepted=False)
        save(folder/'candidate-event-profile.json', doc)
        save(folder/'original-event-profile.json', original)
        for i, ax in enumerate(axes[:, column]):
            ax.plot(time, reference[i], color='black', lw=1.2, label='material excess')
            for label, color in [('old', '#c15a36'), ('candidate', '#247592')]:
                values = np.array(curves[label])[:, i]
                ax.plot(time, values.mean(axis=0), color=color, lw=1, label=label)
                ax.fill_between(time, values.min(axis=0), values.max(axis=0), color=color, alpha=.12)
            ax.set_title(kind+' / '+str(bands[i]['hz'])+' Hz')
            ax.set_xlabel('seconds within fixed crop')
            if not i:
                ax.legend(fontsize=7)
        report['cases'].append(dict(kind=kind, document=entry['document'], document_sha256=entry['document_sha256'],
            source=source, background=background, observation_frames=len(x), bands=bands,
            fitting=fitting, native=native_rows, eligible_for_optional_authoring=eligible,
            candidate_parameters_sha256=fixed, adopted=False))
        save(out/'report.json', report)
    fig.savefig(out/'temporal.png', dpi=160)
    plt.close(fig)
    runtime = load(root/'A_exterior_startup_v1/selection1/runtime.json')
    assert len(runtime) == 459 and all(sha(repo/name) == digest for name, digest in runtime.items())
    report.update(result='passed', runtime_voice_files_unchanged=459,
        qualified_cases=[c['kind'] for c in report['cases'] if c['eligible_for_optional_authoring']])
    save(out/'report.json', report)
    print('one candidate per source completed; eligible', report['qualified_cases'], flush=True)


if __name__ == '__main__':
    main()
