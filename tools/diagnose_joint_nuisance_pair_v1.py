"""Construct joint nuisance compensation at the existing finite common-phase pairs."""
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
from joint_nuisance_pair_v1.model import from_original
from joint_nuisance_pair_v1.fit import fit
from joint_nuisance_pair_v1.checks import check


def load(path):
    return json.loads(path.read_text(encoding='utf-8'))


def save(path, value):
    path.write_text(json.dumps(value, indent=2, allow_nan=False)+'\n', encoding='utf-8', newline='\n')


args.out.mkdir(parents=True, exist_ok=False)
report = dict(schema='vsl.joint-nuisance-pair/1', result='running', sources={}, cases=[],
    real_audio_read=False, truth_used=False, heldout_used=False, phase_estimator_run=False,
    nonlinear_nuisance_fits_run=False, phase_estimator_qualified=False, model_exported=False, runtime_changed=False)
try:
    parent = load(args.parent/'report.json')
    assert parent['result'] == 'finite_envelope_compensation_certified_not_phase_qualification'
    paths = {Path(__file__), repo/'research/joint_nuisance_pair_v1_plan.json',
             *sorted((repo/'tools/joint_nuisance_pair_v1').glob('*.py'))}
    for relative, digest in parent['sources'].items():
        assert sha(repo/relative) == sha(args.parent/'exact_sources'/relative) == digest
        paths.add(repo/relative)
    for path in paths:
        relative = path.relative_to(repo)
        destination = args.out/'exact_sources'/relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, destination)
        report['sources'][relative.as_posix()] = sha(path)
    for filename, key in [('input.npz', 'native_input_sha256'), ('effective_plan.json', 'native_plan_sha256'),
                          ('effective_settings.json', 'native_settings_sha256')]:
        assert sha(args.native/filename) == parent[key]
        report[key] = parent[key]
    report.update(parent_report_sha256=sha(args.parent/'report.json'),
        numeric_libraries=dict(numpy=np.__version__, scipy=scipy.__version__, clarabel=clarabel.__version__))
    settings = load(args.native/'effective_settings.json')
    report['controls'] = check(settings)
    save(args.out/'controls.json', report['controls'])
    if not report['controls']['passed']:
        raise ArithmeticError('Original-gate known joint-nuisance controls failed')
    inputs = np.load(args.native/'input.npz')
    plan, variant = load(args.native/'effective_plan.json'), load(repo/'research/minority_phase_v1_plan.json')
    original = QuinticAbsoluteModel(inputs['time'], plan, variant, [])
    target = original.original.samples(inputs['initial_parameters'])[0]
    report['nonlinear_nuisance_fits_run'] = True
    for published in parent['cases']:
        key = published['id']
        source = args.parent/(key+'.npz')
        assert sha(source) == published['arrays_sha256']
        saved = np.load(source)
        assert np.array_equal(saved['target'], target)
        parameters = saved['parameters']
        model, initial, indices = from_original(original, parameters)
        assert model.size == 648
        assert np.array_equal(model.samples(initial), saved['waveform'])
        def progress(row):
            save(args.out/(key+'_progress.json'), row)
            print(json.dumps(dict(case=key, iteration=row['iteration'], accepted=row['accepted'],
                cost=row['candidate_cost'], certificate=row['subproblem']['certificate']['success'])), flush=True)
        started = timer.perf_counter()
        fitted, result = fit(model, target, initial, settings, progress)
        candidate = parameters.copy()
        candidate[indices] = fitted
        waveform, phase, envelope = original.original.samples(candidate)
        assert np.array_equal(phase, original.original.samples(parameters)[1])
        assert np.array_equal(waveform, model.samples(fitted))
        lower, upper = original.original.bounds(plan, variant)
        violation = float(max(0., (lower-candidate).max(), (candidate-upper).max()))
        case = dict(id=key, seconds=timer.perf_counter()-started, fit=result,
            original_parameter_violation=violation, minimum_envelope=float(envelope.min()),
            minimum_coordinate_step=float(np.diff(inputs['time']+phase).min()),
            common_phase_fixed=True, raw_difference_norm_before=published['raw_difference_norm_after'],
            raw_difference_norm_after=float(np.linalg.norm(waveform-target)))
        case['feasible'] = bool(violation <= settings['maximum_primal_violation']
            and envelope.min() > 0 and case['minimum_coordinate_step'] > 0)
        np.savez_compressed(args.out/(key+'.npz'), parameters=candidate, initial_parameters=parameters,
            nuisance_indices=indices, nuisance_parameters=fitted, initial_nuisance_parameters=initial,
            waveform=waveform, target=target, time=inputs['time'])
        case['arrays_sha256'] = sha(args.out/(key+'.npz'))
        report['cases'].append(case)
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
        before, after = np.load(args.parent/(key+'.npz')), np.load(args.out/(key+'.npz'))
        axes[0].plot(inputs['time'], before['waveform']-target, linewidth=.6, label=key+' fixed angles')
        axes[1].plot(inputs['time'], after['waveform']-target, linewidth=.6, label=key+' joint nuisance')
    axes[0].set(title='Same fixed common-phase pairs; joint a/b and slow-envelope compensation', ylabel='Before joint fit')
    axes[1].set(xlabel='Coarse-cycle coordinate', ylabel='After joint fit')
    for axis in axes:
        axis.legend(fontsize=8)
    figure.savefig(args.out/'joint_nuisance_pairs.png', dpi=150)
    plt.close(figure)
    complete = all(row['feasible'] and row['fit']['every_subproblem_certified'] for row in report['cases'])
    report.update(result='finite_joint_nuisance_pairs_measured_not_global_minima' if complete else
        'finite_joint_nuisance_pairs_numerically_unqualified',
        known_raw_white_sigma_for_fresh_fixed_hypotheses=sigma,
        plot_sha256=sha(args.out/'joint_nuisance_pairs.png'),
        limitations=['Fixed common-phase direction; finite local joint compensation is not a global nuisance minimum or phase recovery',
            'Convex subproblem certificates do not prove nonlinear convergence or all physical source identifiability',
            'Fixed-pair distances assume fresh independent synthetic white noise, not original-data confidence or real-noise calibration',
            'Failed dense positive/all17/full33/individual14kHz/original E remain required before real phase-extracted models'])
    print(json.dumps(dict(result=report['result'], norms=[r['raw_difference_norm_after'] for r in report['cases']])), flush=True)
except Exception as exc:
    report.update(result='failed', error=repr(exc))
    raise
finally:
    save(args.out/'report.json', report)
