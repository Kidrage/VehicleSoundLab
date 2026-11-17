"""One source fit per declared startup crop; held-out results never refit."""
import argparse
from pathlib import Path
import shutil

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import soundfile as sf

from audit_startup_contour_ensemble_v1 import powers
from event_authoring.audio import read
from event_authoring.contour_all_bands import observations
from event_authoring.contour_ensemble import baseline_errors
from event_authoring.measure import observe
from event_authoring.model import synth
from event_authoring.native import Renderer, controls
from event_authoring.response_ensemble import target_powers
from event_authoring.response_fit import EDGES as SPECTRAL_EDGES
from event_band_texture.profile import TRAIN_SEEDS, HELD_OUT_SEEDS, design
from event_band_texture.voice import render
from event_band_texture.fit import solve, solve_conditioned
from research_archive_v1 import load, save, sha


def assess(wave, targets, reference, baseline):
    energy = powers(wave, 1024).mean(axis=1)
    total = float(targets.sum())
    significant = targets >= total*1e-4
    db = 10*np.log10(np.maximum(energy, 1e-30)/np.maximum(targets, 1e-30))
    passed = np.where(significant, abs(db) <= 3, energy <= np.maximum(targets*2, total*2e-4))
    curve = powers(wave, 240)[1:5]
    normalized = curve/np.maximum(curve.mean(axis=1), 1e-30)[:, None]
    rmse = np.sqrt(np.mean((normalized-reference)**2, axis=1))
    nonregression = bool(np.all(rmse <= np.asarray(baseline)+1e-10))
    return dict(bands=[dict(hz=list(edge), error_db=float(error), passed=bool(ok),
        generated_power=float(actual), target_power=float(wanted))
        for edge, error, ok, actual, wanted in zip(SPECTRAL_EDGES, db, passed, energy, targets)],
        shape_rmse=rmse.tolist(), temporal_nonregression=nonregression,
        qualified=bool(passed.all() and nonregression)), normalized


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--conditioned', action='store_true')
    args = parser.parse_args()
    out = args.output
    out.mkdir(parents=True, exist_ok=False)
    repo = Path(__file__).resolve().parents[1]
    root = Path('E:/VehicleSoundLab/references/analysis')
    known = root/'startup_band_texture_v1'/('conditioning-known1' if args.conditioned else 'known2')
    assert load(known/'report.json')['result'] == 'passed'
    for p in (repo/'tools/event_band_texture').glob('*.py'):
        assert sha(p) == sha(known/'exact_sources'/p.relative_to(repo))
    for p in [Path(__file__), repo/'research/startup_band_texture_v1_plan.json',
              repo/'research/event_texture_conditioning_v1_plan.json',
              *sorted((repo/'tools/event_band_texture').glob('*.py'))]:
        dest = out/'exact_sources'/p.relative_to(repo)
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(p, dest)
    report = dict(result='running', known_first_report=str(known/'report.json'),
        known_first_report_sha256=sha(known/'report.json'), cases=[],
        conditioned_coordinates=args.conditioned,
        runtime_integrated=False, goal_complete=False, timbre_accepted=False)
    save(out/'report.json', report)
    renderer = Renderer(repo)
    baseline = load(root/'startup_contour_ensemble_v1/baseline1/report.json')
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
        duration = len(x)/rate
        _, arrays = observe(x, bg)
        time, target, bands = observations(x, bg)
        assert all(b['selected'] for b in bands)
        reference = target/np.maximum(target.mean(axis=1), 1e-30)[:, None]
        targets = target_powers(arrays)
        designed, colour = design(original['parameters'], arrays, time, target, bands, duration)
        save(folder/'designed-profile.json', designed)
        legacy = baseline_errors(original['parameters'], reference, duration, TRAIN_SEEDS)
        print(kind, 'one band-limited colour/contour fit begins', flush=True)
        fitting_function = solve_conditioned if args.conditioned else solve
        candidate, fitting = fitting_function(designed, reference, list(range(4)), targets, legacy, duration)
        saved_candidate = folder/'candidate-before-validation.json'
        save(saved_candidate, candidate)
        save(folder/'training-before-validation.json', fitting)
        candidate_hash = sha(saved_candidate)
        seed_rows, curves = [], {'old_C': [], 'candidate_Python': []}
        held_out = (14741, 38011, 73013, 98717) if args.conditioned else HELD_OUT_SEEDS
        for seed in (*TRAIN_SEEDS, *held_out):
            old, _ = renderer.render(original['parameters'], kind, controls(dict(seed=seed,
                seconds=duration+.15, hold_seconds=duration)))
            expected = synth(original['parameters'], seed=seed, seconds=duration+.15,
                release_at=duration if original['parameters']['gated'] else None)
            expected = np.pad(expected, (0, len(old)-len(expected)))
            c_error = float(np.max(abs(old-expected)))
            assert c_error < 3e-6
            generated = render(candidate, duration+.15, seed,
                release_at=duration if original['parameters']['gated'] else None)
            old_metrics, old_curve = assess(old[:len(x)], targets, reference, [1e30]*4)
            new_metrics, new_curve = assess(generated[:len(x)], targets, reference, old_metrics['shape_rmse'])
            for label, wave in [('old_C', old), ('candidate_Python', generated)]:
                sf.write(folder/(label+'-'+str(seed)+'.wav'), wave, rate, subtype='FLOAT')
            old_metrics['C_python_max_error_FS'] = c_error
            seed_rows.append(dict(seed=seed, split='training' if seed in TRAIN_SEEDS else 'held_out',
                old=old_metrics, candidate=new_metrics,
                candidate_peak_FS=float(np.max(abs(generated)))))
            curves['old_C'].append(old_curve)
            curves['candidate_Python'].append(new_curve)
        assert sha(saved_candidate) == candidate_hash
        old_rmse = np.array([r['old']['shape_rmse'] for r in seed_rows[:4]])
        new_rmse = np.array([r['candidate']['shape_rmse'] for r in seed_rows[:4]])
        base = np.mean((old_rmse/np.maximum(old_rmse, .05))**2)
        score = np.mean((new_rmse/np.maximum(old_rmse, .05))**2)
        improvement = float((base-score)/base)
        eligible = bool(improvement > 1e-5 and all(row['candidate']['qualified'] for row in seed_rows))
        sf.write(folder/'source-reference.wav', x, rate, subtype='FLOAT')
        save(folder/'original-event-profile.json', original)
        for index, ax in enumerate(axes[:, column]):
            ax.plot(time, reference[index], color='black', lw=1.2, label='source excess')
            for label, color in [('old_C', '#b85232'), ('candidate_Python', '#287591')]:
                values = np.asarray(curves[label])[:, index]
                ax.plot(time, values.mean(axis=0), color=color, label=label, lw=1)
                ax.fill_between(time, values.min(axis=0), values.max(axis=0), color=color, alpha=.12)
            ax.set_title(kind+' / '+str(bands[index]['hz'])+' Hz')
            ax.set_xlabel('seconds within fixed crop')
            if not index:
                ax.legend(fontsize=7)
        report['cases'].append(dict(kind=kind, document=entry['document'], document_sha256=entry['document_sha256'],
            source=source, background=background, observation_frames=len(x), bands=bands, colour=colour,
            fitting=fitting, seeds=seed_rows, candidate_parameters_sha256=candidate_hash,
            relative_legacy_shape_improvement=improvement, eligible_for_C_prototype=eligible,
            adopted=False, physical_identity_or_RPM_inferred=False))
        save(out/'report.json', report)
        print(kind, 'eligible', eligible, 'shape improvement', improvement, flush=True)
    fig.savefig(out/'temporal.png', dpi=160)
    plt.close(fig)
    runtime = load(root/'A_exterior_startup_v1/selection1/runtime.json')
    assert len(runtime) == 459 and all(sha(repo/name) == digest for name, digest in runtime.items())
    report.update(result='passed', runtime_voice_files_unchanged=459,
        qualified_cases=[c['kind'] for c in report['cases'] if c['eligible_for_C_prototype']])
    save(out/'report.json', report)
    print('declared fits complete; C-prototype candidates', report['qualified_cases'], flush=True)


if __name__ == '__main__':
    main()
