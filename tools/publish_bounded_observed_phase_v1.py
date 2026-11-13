"""Fixed-pair cross evaluation and phase/edge plots; no additional fitting."""
import argparse
import json
import math
from pathlib import Path
import shutil
import sys

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--workspace', type=Path, required=True); p.add_argument('--out', type=Path, required=True)
args = p.parse_args(); repo = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(args.workspace/'tools/python_deps')]
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from drive_evidence_v1.sources import sha
from quintic_phase_v1.model import QuinticAbsoluteModel
from correlated_observation_v1.marginal import MarginalAperture
from aperture_model_v1.forward import real_rows
from complex_radial_v1.loss import cost


def load(path): return json.loads(path.read_text(encoding='utf-8'))


args.out.mkdir(parents=True, exist_ok=False)
report = dict(schema='vsl.bounded-observed-phase-review/1', result='running', sources={}, comparisons=[],
    real_audio_read=False, truth_used=False, heldout_used=False, nonlinear_fits_run=False,
    model_exported=False, runtime_changed=False, full_qualification=False)
try:
    root = args.workspace/'references/analysis/bounded_observed_phase_v1'
    pair = load(root/'pair2/report.json'); audit = load(root/'audit1/report.json')
    assert audit['all_actual40_steps_audited'] and audit['candidate_report_sha256'] == sha(root/'pair2/report.json')
    paths = {Path(__file__), repo/'research/bounded_observed_phase_v1_cross_plan.json'}
    for name, digest in audit['sources'].items():
        assert sha(repo/name) == sha(root/'audit1/exact_sources'/name) == digest; paths.add(repo/name)
    for path in paths:
        relative = path.relative_to(repo); dest = args.out/'exact_sources'/relative
        dest.parent.mkdir(parents=True, exist_ok=True); shutil.copy2(path, dest)
        report['sources'][relative.as_posix()] = sha(path)
    parent = args.workspace/'references/analysis/complex_radial_v1/fit1'
    input_data = np.load(parent/'input.npz'); arrays = np.load(root/'pair2/direction.npz')
    plan = load(parent/'effective_plan.json'); variant = load(repo/'research/minority_phase_v1_plan.json')
    time = input_data['time']; interior = (time >= 5)&(time < 35)
    model = QuinticAbsoluteModel(time, plan, variant, []); m = model.original
    parameters = {key: arrays['base_parameters' if key == 'baseline' else key+'_parameters'] for key in ('baseline', 'minus', 'plus')}
    waves = {}; phases = {}; scalar_errors = {}
    for key, fitted in parameters.items():
        wave, phase, envelope = m.samples(fitted); waves[key] = wave; phases[key] = phase
        first = 2*m.parts+m.phase_count
        beta = fitted[first:m.base_count].reshape(m.parts, m.envelope_count)
        # Independent scalar trigonometric synthesis; parameters already frozen.
        independent = np.array([math.fsum((1+math.fsum(float(a*b) for a, b in zip(m.envelope_basis[k], beta[j])))*
            (float(fitted[j])*math.cos(2*math.pi*float(m.orders[j])*float(time[k]+phase[k]))+
             float(fitted[j+m.parts])*math.sin(2*math.pi*float(m.orders[j])*float(time[k]+phase[k])))
            for j in range(m.parts)) for k in range(len(time))])
        error = float(abs(independent-wave).max()); assert error <= 1e-12
        scalar_errors[key] = error
    assert np.array_equal(waves['baseline'], arrays['target_waveform'])
    for metric in ('native', 'marginal'):
        if metric == 'marginal': m.aperture = MarginalAperture(m.aperture)
        observed = real_rows(m.aperture.apply(input_data['audio'][:, 0]))
        baseline = real_rows(m.aperture.apply(waves['baseline']))
        for key in ('baseline', 'minus', 'plus'):
            value = real_rows(m.aperture.apply(waves[key])); residual = value-observed
            direct = m.aperture.apply(waves[key]-input_data['audio'][:, 0])
            power = direct.real**2+direct.imag**2
            independent_cost = float(np.sum(power/(np.sqrt(1+power/plan['soft_l1_scale']**2)+1)))
            actual_cost = cost(residual, plan['soft_l1_scale'])
            assert abs(independent_cost-actual_cost) <= 1e-12*max(1., actual_cost)
            difference = value-baseline; direct_difference = real_rows(m.aperture.apply(waves[key]-waves['baseline']))
            closure = float(abs(difference-direct_difference).max()); assert closure <= 1e-12
            report['comparisons'].append(dict(metric=metric, model=key, radial_original_data_cost=actual_cost,
                independent_cost_absolute_error=abs(independent_cost-actual_cost), observation_difference_norm=float(np.linalg.norm(difference)),
                raw_difference_norm=float(np.linalg.norm(waves[key]-waves['baseline'])),
                original_data_projection_residual_norm=float(np.linalg.norm(residual)), difference_projection_closure=closure))
    figure, axes = plt.subplots(3, 1, figsize=(11, 8), layout='constrained')
    for key in ('minus', 'plus'):
        delta = phases[key]-phases['baseline']; delta -= np.median(delta[interior])
        axes[0].plot(time, delta, label=key)
        axes[1].plot(time[interior], delta[interior], label=key)
        axes[2].plot(time, waves[key]-waves['baseline'], linewidth=.55, label=key+' after bounded compensation')
    for axis in axes:
        axis.axvspan(0, 5, color='gray', alpha=.12); axis.axvspan(35, 40, color='gray', alpha=.12)
        axis.set_xlim(0, 40); axis.legend(fontsize=8)
    axes[0].set(title='One observed conditional weak direction, finite targets at phase-p95 = 0.0002 cycles',
        ylabel='Phase difference (cycles)')
    axes[1].set(xlim=(5, 35), ylabel='Interior phase difference',
        title='Interior view; two signs use the same predeclared magnitude')
    axes[2].set(xlabel='Coarse-cycle coordinate', ylabel='Raw waveform difference',
        title='All samples were used in compensation; shaded regions are original phase-evaluation edges')
    figure.savefig(args.out/'bounded_observed_phase.png', dpi=150); plt.close(figure)
    report.update(result='fixed_observed_pairs_cross_evaluated_and_published_no_estimator_change',
        reports_sha256={n: sha(root/n/'report.json') for n in ('pair1', 'pair2', 'audit1')},
        scalar_waveform_maximum_errors=scalar_errors,
        plot_sha256=sha(args.out/'bounded_observed_phase.png'),
        limits=['Same fixed baseline/minus/plus parameters, no refit/rescale or trimmed compensation',
            'Compare objective values only within the same metric; no timbre or calibrated noise-distance claim',
            'Synthetic input only; no true phase/noise decomposition/heldout values are read',
            'One direction does not certify all directions, original dense36 or real DNA'])
    print(json.dumps(dict(result=report['result'], comparisons=report['comparisons'])), flush=True)
except Exception as exc:
    report.update(result='failed', error=repr(exc)); raise
finally:
    (args.out/'report.json').write_text(json.dumps(report, indent=2, allow_nan=False)+'\n', encoding='utf-8', newline='\n')
