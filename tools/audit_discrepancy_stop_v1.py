"""Independently reconstruct the observed discrepancy crossing and saved phase."""
import argparse
import json
from pathlib import Path
import shutil
import sys

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--workspace', type=Path, required=True)
parser.add_argument('--parent', type=Path, required=True)
parser.add_argument('--noise', type=Path, required=True)
parser.add_argument('--candidate', type=Path, required=True)
parser.add_argument('--out', type=Path, required=True)
args = parser.parse_args()
repo = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(args.workspace/'tools/python_deps'))
import numpy as np
from drive_evidence_v1.sources import sha
from quintic_phase_v1.model import QuinticAbsoluteModel
from aperture_model_v1.forward import real_rows
from aperture_model_v1.checks import assess


def load(path):
    return json.loads(path.read_text(encoding='utf-8'))


args.out.mkdir(parents=True, exist_ok=False)
report = dict(schema='vsl.discrepancy-stop-audit/1', result='running', sources={},
    real_audio_read=False, real_source_permitted=False, qualification_changed=False,
    nonlinear_estimator_rerun=False, quadratic_solver_rerun=False)
try:
    parent, candidate = load(args.parent/'report.json'), load(args.candidate/'report.json')
    assert candidate['result'] == 'discrepancy_prefix_rejected'
    assert candidate['parent_report_sha256'] == sha(args.parent/'report.json')
    assert candidate['noise_report_sha256'] == sha(args.noise/'report.json')
    for relative, digest in candidate['sources'].items():
        assert sha(repo/relative) == sha(args.candidate/'exact_sources'/relative) == digest
    for path in [Path(__file__)]+[repo/name for name in candidate['sources']]:
        relative = path.relative_to(repo)
        target = args.out/'exact_sources'/relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, target)
        report['sources'][relative.as_posix()] = sha(path)
    observed = np.load(args.noise/'input.npz')
    original = np.load(args.parent/'fit.npz')
    time, audio = observed['time'], observed['original_observed_audio']
    plan = load(args.parent/'effective_plan.json')
    variant = load(repo/'research/minority_phase_v1_plan.json')
    model = QuinticAbsoluteModel(time, plan, variant, [])
    channel = audio[:, 0]
    n = len(channel)
    window = .5-.5*np.cos(2*np.pi*np.arange(n)/n)
    frequency = np.fft.fftfreq(n)
    selected = (frequency >= .75*.5)&(frequency < .5)
    power = abs(np.fft.fft(channel*window))**2/(window@window)
    variance = float(np.median(power[selected])/np.log(2))
    aperture = model.original.aperture
    trace = float(len(aperture.starts)*len(aperture.orders)*4*
        np.sum(aperture.window**2)/aperture.window.sum()**2)
    budget = variance*trace
    assert abs(budget/candidate['selection']['expected_noise_energy']-1) < 1e-12
    target = real_rows(aperture.apply(channel))
    # The selector module is deliberately not imported or called here.
    outer, amplitudes = model.unpack(original['initial_parameters'])
    states = [(0, outer, amplitudes)]+[(row['iteration'], np.asarray(row['candidate_outer']),
        np.asarray(row['candidate_absolute_amplitudes'])) for row in parent['fit']['history'] if row['accepted']]
    examined = []
    for iteration, outer, amplitudes in states:
        residual = model.prediction(outer, amplitudes)-target
        energy = float(residual@residual)
        examined.append(dict(iteration=iteration, residual_energy=energy))
        if energy <= budget:
            break
    else:
        raise AssertionError('Independent reconstruction found no crossing')
    assert examined == candidate['selection']['examined']
    assert iteration == candidate['selection']['selected_iteration'] == 1
    parameters = model.pack(outer, amplitudes)
    saved = np.load(args.candidate/'selected.npz')
    _, phase, _ = model.original.samples(parameters)
    assert np.array_equal(parameters, saved['parameters']) and np.array_equal(phase, saved['phase_correction'])
    evaluation = {**plan, 'heldout_orders': load(repo/'research/aperture_model_v1_plan.json')['heldout_orders']}
    assessment, positions, oracle = assess(audio, time, original['true_phase_correction'], phase, parameters, evaluation)
    assert assessment == candidate['assessment'] and not assessment['qualified']
    assert np.array_equal(positions, saved['positions']) and np.array_equal(oracle, saved['oracle_positions'])
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    interior = (time >= 5)&(time < 35)
    fig, axis = plt.subplots(figsize=(10, 4), layout='constrained')
    for label, curve in (('Original 20-step fit', original['phase_correction']), ('Observed discrepancy stop', phase)):
        error = curve-original['true_phase_correction']
        error -= np.median(error[interior])
        axis.plot(time[interior], error[interior], label=label)
    for sign in (-1, 1):
        axis.axhline(sign*plan['rules']['maximum_point_phase_p95_cycles'], color='k', linestyle='--', linewidth=.7)
    axis.set(xlabel='Coarse-cycle coordinate', ylabel='Median-aligned phase error (cycles)')
    axis.legend()
    fig.savefig(args.out/'discrepancy_phase.png', dpi=150)
    plt.close(fig)
    report.update(result='observed_discrepancy_crossing_and_rejected_assessment_reconstructed',
        candidate_report_sha256=sha(args.candidate/'report.json'), observed_only_crossing_exact=True,
        full_complex_FFT_budget_relative_error=float(abs(budget/candidate['selection']['expected_noise_energy']-1)),
        selected_parameters_phase_and_assessment_exact=True, examined=examined, selected_iteration=iteration,
        assessment=assessment, original_gates_unchanged=True, plot_sha256=sha(args.out/'discrepancy_phase.png'))
    print(json.dumps(dict(result=report['result'], selected_iteration=iteration,
        phase_p95_cycles=assessment['point_phase_p95_cycles'])), flush=True)
except Exception as exc:
    report.update(result='failed', error=repr(exc))
    raise
finally:
    (args.out/'report.json').write_text(json.dumps(report, indent=2, allow_nan=False)+'\n', encoding='utf-8', newline='\n')
