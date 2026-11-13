"""Measure finite slow-envelope compensation under every original amplitude bound."""
import argparse
import json
from pathlib import Path
import shutil
import sys
import time as timer

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--workspace', type=Path, required=True)
parser.add_argument('--native', type=Path, required=True)
parser.add_argument('--parent', type=Path, required=True)
parser.add_argument('--out', type=Path, required=True)
args = parser.parse_args()
repo = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(args.workspace/'tools/ipm_deps'), str(args.workspace/'tools/qp_deps'),
               str(args.workspace/'tools/python_deps')]
import numpy as np
import scipy
import clarabel
from drive_evidence_v1.sources import sha
from quintic_phase_v1.model import QuinticAbsoluteModel
from bounded_envelope_pair_v1.checks import controls as known_controls
from bounded_envelope_pair_v1.solve import fit


def load(path):
    return json.loads(path.read_text(encoding='utf-8'))


def save(path, value):
    path.write_text(json.dumps(value, indent=2, allow_nan=False)+'\n', encoding='utf-8', newline='\n')


args.out.mkdir(parents=True, exist_ok=False)
report = dict(schema='vsl.bounded-envelope-pair/1', result='running', sources={}, cases=[],
    real_audio_read=False, truth_used=False, heldout_used=False, phase_estimator_run=False,
    convex_amplitude_QPs_run=True, phase_estimator_qualified=False, model_exported=False, runtime_changed=False)
try:
    parent = load(args.parent/'report.json')
    assert parent['result'] == 'finite_bounded_clock_pairs_measured_not_phase_qualification'
    assert parent['native_input_sha256'] == sha(args.native/'input.npz')
    assert parent['native_plan_sha256'] == sha(args.native/'effective_plan.json')
    assert parent['pairs_sha256'] == sha(args.parent/'pairs.npz')
    paths = {Path(__file__), repo/'research/bounded_envelope_pair_v1_plan.json',
        *sorted((repo/'tools/bounded_envelope_pair_v1').glob('*.py'))}
    for relative, digest in parent['sources'].items():
        assert sha(repo/relative) == sha(args.parent/'exact_sources'/relative) == digest
        paths.add(repo/relative)
    for path in paths:
        relative = path.relative_to(repo)
        target = args.out/'exact_sources'/relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, target)
        report['sources'][relative.as_posix()] = sha(path)
    plan = load(args.native/'effective_plan.json')
    settings = load(args.native/'effective_settings.json')
    variant = load(repo/'research/minority_phase_v1_plan.json')
    report.update(parent_report_sha256=sha(args.parent/'report.json'),
        native_input_sha256=sha(args.native/'input.npz'), native_plan_sha256=sha(args.native/'effective_plan.json'),
        native_settings_sha256=sha(args.native/'effective_settings.json'),
        numeric_libraries=dict(numpy=np.__version__, scipy=scipy.__version__, clarabel=clarabel.__version__))
    report['controls'] = known_controls(settings)
    if not report['controls']['passed']:
        raise ArithmeticError('Closed-form original-bound amplitude controls failed')
    inputs = np.load(args.native/'input.npz')
    model = QuinticAbsoluteModel(inputs['time'], plan, variant, [])
    saved = np.load(args.parent/'pairs.npz')
    target = saved['base_waveform']
    assert np.array_equal(model.original.samples(inputs['initial_parameters'])[0], target)
    for key, parent_case in zip(('minus', 'plus'), parent['cases']):
        parameters = saved[key+'_parameters']
        outer, initial_controls = model.unpack(parameters)
        cosine = model.carrier(outer)[0]
        design = (cosine[:, :, None]*model.full[:, None, :]).reshape(len(cosine), -1)
        assert design.shape == (5120, 612)
        assert abs(design@initial_controls.ravel()-saved[key+'_waveform']).max() <= 1e-12
        started = timer.perf_counter()
        amplitude, result = fit(design, target, initial_controls, model.bound, model.caps(outer), settings)
        seconds = timer.perf_counter()-started
        candidate = model.pack(outer, amplitude)
        waveform, phase, envelope = model.original.samples(candidate)
        phase_before = model.original.samples(parameters)[1]
        assert np.array_equal(phase, phase_before)
        source_error = float(abs(waveform-design@amplitude.ravel()).max())
        lower, upper = model.original.bounds(plan, variant)
        violation = float(max(0., (lower-candidate).max(), (candidate-upper).max()))
        interior = (inputs['time'] >= 5)&(inputs['time'] < 35)
        phase_delta = phase-model.original.samples(inputs['initial_parameters'])[1]
        phase_delta -= np.median(phase_delta[interior])
        case = dict(id=key, sign=parent_case['sign'], seconds=seconds, fit=result,
            original_parameter_violation=violation, raw_sample_pack_maximum_error=source_error,
            phase_and_carrier_angles_fixed=True, minimum_envelope=float(envelope.min()),
            minimum_coordinate_step=float(np.diff(inputs['time']+phase).min()),
            phase_difference_p95_cycles=float(np.percentile(abs(phase_delta[interior]), 95)),
            raw_difference_norm_before=parent_case['raw_difference_norm_after'],
            raw_difference_norm_after=float(np.linalg.norm(waveform-target)),
            maximum_absolute_amplitude_control_change=float(abs(amplitude-initial_controls).max()))
        case['feasible'] = bool(violation <= settings['maximum_primal_violation']
            and envelope.min() > 0 and case['minimum_coordinate_step'] > 0 and source_error <= 1e-12)
        np.savez_compressed(args.out/(key+'.npz'), parameters=candidate, waveform=waveform,
            absolute_controls=amplitude, initial_absolute_controls=initial_controls,
            fixed_outer=outer, target=target, time=inputs['time'])
        case['arrays_sha256'] = sha(args.out/(key+'.npz'))
        report['cases'].append(case)
        save(args.out/'progress.json', case)
        print(json.dumps(dict(case=key, seconds=seconds, feasible=case['feasible'],
            certificate=result['certificate'], raw_norm=case['raw_difference_norm_after'])), flush=True)
    # Only diagnostic evaluation reads the already declared synthetic sigma.
    topology = load(repo/'research/observed_topology_v1_plan.json')
    fixture = next(row for row in topology['added_cases'] if row['id'] == 'unknown_thirty_six')
    sigma = fixture['noise']*fixture['gain']
    for row in report['cases']:
        row['fixed_hypothesis_distance_under_fresh_white_noise'] = row['raw_difference_norm_after']/sigma
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    figure, axes = plt.subplots(2, 1, figsize=(10, 6), layout='constrained')
    for key in ('minus', 'plus'):
        values = np.load(args.out/(key+'.npz'))
        axes[0].plot(inputs['time'], saved[key+'_waveform']-target, label=key+' fixed envelope', linewidth=.6)
        axes[1].plot(inputs['time'], values['waveform']-target, label=key+' free bounded envelope', linewidth=.6)
    axes[0].set(title='Same finite common-clock perturbations; all original bounds retained', ylabel='Before envelope compensation')
    axes[1].set(xlabel='Coarse-cycle coordinate', ylabel='After envelope compensation')
    for axis in axes:
        axis.legend(fontsize=8)
    figure.savefig(args.out/'bounded_envelope_pairs.png', dpi=150)
    plt.close(figure)
    complete = all(row['feasible'] and row['fit']['certificate']['success'] for row in report['cases'])
    report.update(result='finite_envelope_compensation_certified_not_phase_qualification' if complete else
        'finite_envelope_compensation_not_numerically_qualified',
        known_raw_white_sigma_for_fresh_fixed_hypotheses=sigma,
        plot_sha256=sha(args.out/'bounded_envelope_pairs.png'),
        limitations=['One fixed common-phase direction and constant angles; no global minimum over all nuisance or phase parameters',
            'Fixed-pair distances assume fresh independent synthetic white noise, not inference on the original data-dependent initialization',
            'Convex amplitude certificates do not establish common-phase recovery, real coloured-noise calibration or vehicle realism',
            'Failed dense positive/all17/full33/individual14kHz/original E remain required before phase-extracted real models'])
    print(json.dumps(dict(result=report['result'], cases=len(report['cases']))), flush=True)
except Exception as exc:
    report.update(result='failed', error=repr(exc))
    raise
finally:
    save(args.out/'report.json', report)
