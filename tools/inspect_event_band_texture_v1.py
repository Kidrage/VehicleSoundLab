"""Read-only spectral-budget diagnostics; no new source fit or candidate."""
import argparse
from pathlib import Path
import shutil

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
from scipy import linalg, optimize, signal

from audit_startup_contour_ensemble_v1 import EDGES, powers
from event_authoring.model import synth
from event_band_texture.fit import Response
from event_band_texture.profile import TRAIN_SEEDS
from research_archive_v1 import load, save, sha


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    repo = Path(__file__).resolve().parents[1]
    for path in [Path(__file__), *sorted((repo/'tools/event_band_texture').glob('*.py'))]:
        dest = args.output/'exact_sources'/path.relative_to(repo)
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, dest)
    # A diagonal fixture establishes the direction of the generalized bound.
    np.testing.assert_allclose(linalg.eigvalsh(np.diag([2., 6.]), np.diag([2., 3.])), [1., 2.])
    fit = load(args.input/'report.json')
    assert fit['result'] == 'passed'
    fig, axes = plt.subplots(2, 2, figsize=(12, 8), layout='constrained')
    rows = []
    for index, case in enumerate(fit['cases']):
        profile = load(args.input/case['kind']/'designed-profile.json')
        targets = np.array([r['target_power'] for r in case['seeds'][0]['old']['bands']])
        seconds = case['observation_frames']/48000
        modal = np.mean([powers(synth(profile['modal'], seed=s, seconds=seconds), 1024).mean(axis=1)
                         for s in TRAIN_SEEDS], axis=0)
        matrix = []
        for band in profile['bands']:
            hz, h = signal.sosfreqz(np.asarray(band['sos']), worN=65536, fs=48000)
            density = abs(h)**2*band['sigma']**2/3/len(hz)
            matrix.append([density[(hz >= low)&(hz < high)].sum() for low, high in EDGES])
        matrix = np.asarray(matrix).T
        scale = np.maximum(targets, targets.sum()*1e-4)
        coefficients, _ = optimize.nnls(matrix/scale[:, None], (targets-modal)/scale)
        stationary = modal+matrix@coefficients
        response = Response(profile, seconds)
        gram = response.spectral.mean(axis=0)
        upper = np.where(targets >= targets.sum()*1e-4, targets*10**.3,
                         np.maximum(2*targets, targets.sum()*2e-4))
        bounds = []
        for band in (0, 5):
            a = gram[band]
            b = gram.sum(axis=0)-a
            eigenvalue = float(linalg.eigvalsh(a, b)[-1])
            safe_bound = eigenvalue*(1+1e-6)
            slack = safe_bound*b-a
            assert np.linalg.eigvalsh(slack)[0] > 0
            necessary = float(targets[band]/10**.3/(upper.sum()-upper[band]))
            bounds.append(dict(band_hz=list(EDGES[band]), maximum_relaxed_power_ratio=safe_bound,
                required_lower_ratio=necessary, denominator_condition=float(np.linalg.cond(b)),
                proves_spectral_infeasibility=bool(necessary > safe_bound)))
        axes[0, index].imshow(10*np.log10(np.maximum(matrix, 1e-16)), vmin=-70, vmax=0,
                              aspect='auto', cmap='magma')
        axes[0, index].set_title(case['kind']+' / stationary band power per unit variance')
        axes[0, index].set_xticks(range(4), ['60-300', '300-1200', '1.2-4.5k', '4.5-14k'], rotation=15)
        axes[0, index].set_yticks(range(6), [str(e) for e in EDGES])
        ax = axes[1, index]
        for value, label, color in [(targets, 'source excess', 'black'),
            (modal, 'fixed modal component', '#c75835'), (stationary, 'stationary NNLS diagnostic', '#277e97')]:
            ax.plot(np.arange(6), 10*np.log10(np.maximum(value, 1e-20)), 'o-', label=label, color=color)
        ax.set_xticks(range(6), ['<60', '60-300', '300-1200', '1.2-4.5k', '4.5-14k', '>14k'], rotation=20)
        ax.set_ylabel('band mean square / dBFS')
        ax.legend(fontsize=7)
        rows.append(dict(kind=case['kind'], source_target_power=targets.tolist(),
            fixed_modal_power=modal.tolist(), fixed_modal_to_target_db=(10*np.log10(np.maximum(modal,1e-30)/targets)).tolist(),
            stationary_noise_power_matrix=matrix.tolist(), diagnostic_variance_weights=coefficients.tolist(),
            stationary_diagnostic_power=stationary.tolist(), generalized_necessary_bounds=bounds,
            finite_problem_infeasibility_proved=any(b['proves_spectral_infeasibility'] for b in bounds)))
    fig.savefig(args.output/'spectral-budget.png', dpi=150)
    plt.close(fig)
    save(args.output/'report.json', dict(result='passed', reviewed_report=str(args.input/'report.json'),
        reviewed_report_sha256=sha(args.input/'report.json'), cases=rows,
        stationary_NNLS_is_diagnostic_only=True, no_candidate_generated_or_qualified=True,
        limitations='Stationary PSD ignores transient envelopes, finite FFT leakage and deterministic cross terms. '
            'Generalized bounds relax coefficient signs and the fixed modal coefficient. A non-rejection is '
            'inconclusive; optimizer failure is not a proof that pure synthesis or this finite model is impossible.',
        goal_complete=False, timbre_accepted=False))
    print('stationary support and necessary spectral bounds recorded; no new fit or candidate', flush=True)


if __name__ == '__main__':
    main()
