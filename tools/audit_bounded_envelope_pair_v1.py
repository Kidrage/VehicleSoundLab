"""Audit saved amplitude solutions in the full original polytope without solving again."""
import argparse
import json
import math
from pathlib import Path
import shutil
import sys

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--workspace', type=Path, required=True)
parser.add_argument('--native', type=Path, required=True)
parser.add_argument('--parent', type=Path, required=True)
parser.add_argument('--candidate', type=Path, required=True)
parser.add_argument('--out', type=Path, required=True)
args = parser.parse_args()
repo = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(args.workspace/'tools/python_deps'))
import numpy as np
from drive_evidence_v1.sources import sha
from quintic_phase_v1.model import QuinticAbsoluteModel


def load(path):
    return json.loads(path.read_text(encoding='utf-8'))


def full_constraints(shape, bound, caps):
    """Independent dense coefficient construction, not the solver's sparse builder."""
    parts, count = shape
    block = np.zeros((2*count-1, count))
    block[0, 0] = 1
    for j in range(1, count):
        block[2*j-1, 0], block[2*j-1, j] = 1-bound, -1
        block[2*j, 0], block[2*j, j] = -1-bound, 1
    matrix = np.kron(np.eye(parts), block)
    lower = np.full(len(matrix), -np.inf)
    upper = np.zeros(len(matrix))
    lower[::len(block)], upper[::len(block)] = 0, caps
    return matrix, lower, upper


def certificate(design, rhs, initial, bound, caps, qp, published, settings):
    matrix, lower, upper = full_constraints(initial.shape, bound, caps)
    center = initial.ravel()
    lower, upper = lower-matrix@center, upper-matrix@center
    x, y, z = (np.asarray(qp[key]) for key in ('primal_solution', 'dual_solution', 'inequality_dual'))
    high, low = np.flatnonzero(np.isfinite(upper)), np.flatnonzero(np.isfinite(lower))
    mapped = np.zeros(len(matrix))
    mapped[high] = z[:len(high)]
    mapped[low] -= z[len(high):]
    assert np.array_equal(y, mapped)
    value = matrix@x
    primal = float(max(0., (lower-value).max(), (value-upper).max()))
    slack = np.concatenate((upper[high]-value[high], value[low]-lower[low]))
    gram, gradient = design.T@design, -design.T@rhs
    maximum = float(abs(gradient).max())
    scale = maximum if maximum > 0 else max(float(abs(gram).max()), 1.)
    assert scale == qp['objective_scale']
    normal = (gram+gram.T)/(2*scale)
    residual = design@x-rhs
    lagrange = matrix.T@y
    measures = dict(primal=primal,
        gram_stationarity=float(abs(normal@x+gradient/scale+lagrange).max()),
        raw_sample_stationarity=float(abs(design.T@residual/scale+lagrange).max()),
        dual_sign=float(max(0., -z.min())), complementarity=float(abs(z*slack).max()),
        quadratic_objective=float(.5*x@gram@x+gradient@x),
        raw_least_squares_objective=float(.5*(residual@residual)))
    measures['raw_quadratic_objective_closure'] = abs(measures['raw_least_squares_objective']-
        (measures['quadratic_objective']+.5*(rhs@rhs)))
    # Independent scalar summation of every sample-space gradient column.
    scalar = np.array([math.fsum(float(a*b) for a, b in zip(column, residual))
                       for column in design.T])/scale+lagrange
    measures['scalar_raw_stationarity'] = float(abs(scalar).max())
    measures['scalar_vs_vector_gradient_error'] = float(abs(scalar-(design.T@residual/scale+lagrange)).max())
    differences = {key: abs(value-published[key]) for key, value in measures.items() if key in published}
    assert max(differences.values()) <= 1e-12
    assert measures['quadratic_objective'] == qp['objective']
    passed = (primal <= settings['maximum_primal_violation'] and
        measures['dual_sign'] <= settings['maximum_primal_violation'] and
        max(measures['gram_stationarity'], measures['raw_sample_stationarity'], measures['scalar_raw_stationarity'])
        <= settings['maximum_normalized_stationarity'] and
        measures['complementarity'] <= settings['maximum_complementarity'] and
        measures['raw_quadratic_objective_closure'] <= 1e-12)
    assert passed and published['success']
    return dict(passed=bool(passed), measurements=measures,
        maximum_published_certificate_error=max(differences.values()),
        rows=int(len(matrix)), columns=int(len(x)), all_constraints_and_duals_checked=True)


args.out.mkdir(parents=True, exist_ok=False)
report = dict(schema='vsl.bounded-envelope-pair-audit/1', result='running', sources={},
    real_audio_read=False, truth_used=False, heldout_used=False, phase_estimator_run=False,
    large_QPs_rerun=False, phase_estimator_qualified=False, model_exported=False, runtime_changed=False)
try:
    candidate, parent = load(args.candidate/'report.json'), load(args.parent/'report.json')
    assert candidate['result'] == 'finite_envelope_compensation_certified_not_phase_qualification'
    assert sha(args.parent/'report.json') == candidate['parent_report_sha256']
    for filename, key in [('input.npz', 'native_input_sha256'), ('effective_plan.json', 'native_plan_sha256'),
                          ('effective_settings.json', 'native_settings_sha256')]:
        assert sha(args.native/filename) == candidate[key]
    paths = {Path(__file__)}
    for relative, digest in candidate['sources'].items():
        assert sha(repo/relative) == sha(args.candidate/'exact_sources'/relative) == digest
        paths.add(repo/relative)
    for path in paths:
        relative = path.relative_to(repo)
        destination = args.out/'exact_sources'/relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, destination)
        report['sources'][relative.as_posix()] = sha(path)
    plan, settings = load(args.native/'effective_plan.json'), load(args.native/'effective_settings.json')
    inputs, parent_arrays = np.load(args.native/'input.npz'), np.load(args.parent/'pairs.npz')
    assert sha(args.parent/'pairs.npz') == parent['pairs_sha256']
    time = inputs['time']
    model = QuinticAbsoluteModel(time, plan, load(repo/'research/minority_phase_v1_plan.json'), [])
    assert (model.parts, model.controls, model.original.parameter_count, model.original.phase_count) == (36, 17, 732, 84)
    target = model.original.samples(inputs['initial_parameters'])[0]
    assert np.array_equal(target, parent_arrays['base_waveform'])
    # Rebuild the complete positive Fejer partition with scalar trig/summation.
    orders = np.asarray(plan['source_orders'])
    period = 2*plan['cycles']
    degree = int(math.floor(period*float(np.diff(orders).min())/2+1e-10))
    count = 2*degree+1
    partition = np.array([[(1+math.fsum(2*(1-k/(degree+1))*math.cos(
        k*2*math.pi*(float(t)/period-j/count)) for k in range(1, degree+1)))/count
        for j in range(count)] for t in time])
    partition_error = float(abs(partition-model.full).max())
    assert degree == 8 and count == 17 and partition_error <= 1e-13
    assert partition.min() >= -1e-12 and abs(partition.sum(axis=1)-1).max() <= 1e-12
    controls = []
    expected = dict(interior=[.4, .4], lower_face=[.4/(1+.75**2), .75*.4/(1+.75**2)],
        upper_face=[1.25*.8/(1+1.25**2), 1.25**2*.8/(1+1.25**2)], cap=[1., 1.25], zero=[0., 0.])
    targets = dict(interior=[.4, .4], lower_face=[.4, 0.], upper_face=[0., .8], cap=[2., 2.], zero=[-.4, -.8])
    for row in candidate['controls']['cases']:
        initial = np.full((1, 2), .5)
        rhs = np.array(targets[row['id']])-initial.ravel()
        result = row['result']
        check = certificate(np.eye(2), rhs, initial, .25, np.ones(1), result['qp'], result['certificate'], settings)
        actual = initial.ravel()+np.asarray(result['qp']['primal_solution'])
        error = float(abs(actual-expected[row['id']]).max())
        assert error == row['maximum_control_error'] and error <= 1e-7 and row['passed']
        controls.append(dict(id=row['id'], analytic_control_error=error, certificate=check))
    cases = []
    for published in candidate['cases']:
        key = published['id']
        path = args.candidate/(key+'.npz')
        assert sha(path) == published['arrays_sha256']
        saved = np.load(path)
        parent_parameters = parent_arrays[key+'_parameters']
        outer, initial = model.unpack(parent_parameters)
        assert np.array_equal(outer, saved['fixed_outer'])
        assert np.array_equal(initial, saved['initial_absolute_controls'])
        assert np.array_equal(saved['target'], target) and np.array_equal(saved['time'], time)
        cosine, _, phase_before = model.carrier(outer)
        design = (cosine[:, :, None]*model.full[:, None, :]).reshape(len(time), -1)
        rhs = target-design@initial.ravel()
        result = published['fit']
        check = certificate(design, rhs, initial, model.bound, model.caps(outer),
                            result['qp'], result['certificate'], settings)
        assert not result['qp']['primal_polish_attempted']
        absolute = initial+np.asarray(result['qp']['primal_solution']).reshape(initial.shape)
        assert np.array_equal(absolute, saved['absolute_controls'])
        parameters = model.pack(outer, absolute)
        assert np.array_equal(parameters, saved['parameters'])
        waveform, phase, envelope = model.original.samples(parameters)
        assert np.array_equal(waveform, saved['waveform']) and np.array_equal(phase, phase_before)
        unpacked, _ = model.unpack(parameters)
        angle_wrap_error = float(abs(np.angle(np.exp(1j*(unpacked[:36]-outer[:36])))).max())
        assert angle_wrap_error <= 1e-12 and np.array_equal(unpacked[36:], outer[36:])
        # Independent original a,b/relative-envelope bounds and waveform summation.
        c0 = absolute[:, 0]
        assert np.all(c0 > 0)
        relative = absolute[:, 1:]/c0[:, None]-1
        assert abs(relative).max() <= .25+settings['maximum_primal_violation']
        assert abs(parameters[:72]).max() <= 1+settings['maximum_primal_violation']
        lower, upper = model.original.bounds(plan, load(repo/'research/minority_phase_v1_plan.json'))
        violation = float(max(0., (lower-parameters).max(), (parameters-upper).max()))
        assert violation == published['original_parameter_violation']
        independent_waveform = np.array([math.fsum(float((partition[n]@absolute[j])*math.cos(
            2*math.pi*(time[n]+phase[n])*orders[j]+outer[j])) for j in range(36)) for n in range(len(time))])
        sample_error = float(abs(independent_waveform-waveform).max())
        assert sample_error <= 1e-12
        assert np.diff(time+phase).min() == published['minimum_coordinate_step'] > 0
        assert envelope.min() == published['minimum_envelope'] > 0
        norm = math.sqrt(math.fsum(float(v*v) for v in waveform-target))
        norm_error = abs(norm-published['raw_difference_norm_after'])
        assert norm_error <= 1e-12
        sigma = candidate['known_raw_white_sigma_for_fresh_fixed_hypotheses']
        distance = norm/sigma
        assert abs(distance-published['fixed_hypothesis_distance_under_fresh_white_noise']) <= 1e-12
        cases.append(dict(id=key, certificate=check, fixed_phase_and_angles_verified=True,
            scalar_raw_waveform_maximum_error=sample_error, norm_error=norm_error,
            fixed_hypothesis_fresh_noise_distance=distance, original_bounds_positive_monotonic=True))
    prior = args.workspace/'references/analysis/bounded_clock_pair_v1/final1'
    for filename in ('C_files_sha256.json', 'voice_files_sha256.json'):
        assert all(sha(repo/path) == digest for path, digest in load(prior/filename).items())
    assert len(load(prior/'C_files_sha256.json')) == 540
    report.update(result='full_bounded_envelope_certificates_controls_and_waveforms_independently_reconstructed',
        candidate_report_sha256=sha(args.candidate/'report.json'), parent_report_sha256=sha(args.parent/'report.json'),
        controls=controls, cases=cases, independent_Fejer_partition_error=partition_error,
        C_H=540, voices_and_moving35_unchanged=True, all_saved_controls_and_parameters_exact=True,
        limitations=candidate['limitations'])
    print(json.dumps(dict(result=report['result'], cases=cases, partition_error=partition_error)), flush=True)
except Exception as exc:
    report.update(result='failed', error=repr(exc))
    raise
finally:
    (args.out/'report.json').write_text(json.dumps(report, indent=2, allow_nan=False)+'\n',
                                      encoding='utf-8', newline='\n')
