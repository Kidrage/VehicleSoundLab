"""Read only independently verified terminal C1 captures.

This adapter does not accept the older PL/sinc128 locked-source identity. It
does not solve, repair, rename, or promote any capture, including failed ones.
"""
from pathlib import Path
import numpy as np
from research_archive_v1 import load, sha
from clock_c1_v1.geometry import evaluate
from observer_frequency_v1.reduced_oracle import synthesize


IDENTITY = 'vsl.c1-declared-native-diagnostic/1'


def terminal(case, proof, *, workspace, known=False):
    case, proof, workspace = map(Path, (case, proof, workspace))
    inputs = {}

    def read(path):
        path = Path(path)
        inputs[str(path)] = sha(path)
        return load(path)

    audit = read(proof/'report.json')
    info = read(case/'report.json')
    if known:
        if (audit.get('result') != 'independent_c1_registered_terminal_known_verified'
                or not audit.get('verification_passed') or not audit.get('all_qualified')):
            raise ValueError('Saved complete C1 declared known proof required')
        label = case.name
        row = next((c for c in audit['cases'] if c['label'] == label), None)
        if row is None:
            raise ValueError('Known case absent from complete terminal proof')
        expected = audit['inputs'].get(str(case/'capture.npz'))
        expected_report = audit['inputs'].get(str(case/'report.json'))
        if expected_report != inputs[str(case/'report.json')]:
            raise ValueError('Known terminal report differs from its saved proof')
        if label != 'nonlinear_zero' and not row.get('verification_passed'):
            raise ValueError('Complete known mathematical verification required')
        if info.get('result') != 'c1_source_known_case_measured':
            raise ValueError('Explicit saved C1 known terminal capture required')
    else:
        claim = case.parent
        receipt = read(claim/'execution_result.json')
        execution = read(claim/'execution_spec.json')
        label = execution['only_label']
        if (receipt.get('result') != 'c1_registered_single_run_complete'
                or audit.get('result') != 'independent_c1_registered_source_verified'
                or not audit.get('verification_passed')
                or not audit['case'].get('solver_qualified')
                or info.get('result') != 'c1_registered_source_measured'):
            raise ValueError('Completed independently verified registered C1 solve required')
        if (receipt['case_report_sha256'] != inputs[str(case/'report.json')]
                or receipt['audit_report_sha256'] != inputs[str(proof/'report.json')]
                or audit['case']['producer_sha256'] != inputs[str(case/'report.json')]
                or info['execution_spec_sha256'] != inputs[str(claim/'execution_spec.json')]
                or execution['measurement_identity'] != 'vsl.c1-declared-objective/1'
                or execution['source_identity'] != 'vsl.c1-22k-source-preparation/1'
                or info['label'] != label
                or case.resolve() != Path(execution['output']).resolve()):
            raise ValueError('C1 terminal execution/report identities differ')
        expected = audit['case']['capture_sha256']
        if sha(info['prepared_file']) != info['prepared_sha256']:
            raise ValueError('C1 prepared source changed after the verified solve')
        inputs[info['prepared_file']] = info['prepared_sha256']
    if expected is None or sha(case/'capture.npz') != expected or info['capture_sha256'] != expected:
        raise ValueError('Terminal C1 capture differs from independent proof')
    inputs[str(case/'capture.npz')] = expected
    with np.load(case/'capture.npz', allow_pickle=False) as f:
        z = {k:f[k] for k in f.files}
    required = ('phase_grid_indices', 'source_coordinates', 'target_source_coordinates',
        'source_filter_taps', 'source_nominal_cutoff_Hz', 'native_rate_Hz',
        'audio', 'target', 'positions', 'orders', 'fitted', 'wave')
    if any(k not in z for k in required):
        raise ValueError('Explicit complete C1 source fields required')
    n = len(z['audio'])
    if (z['audio'].shape != (n, 2) or not np.array_equal(z['phase_grid_indices'], np.arange(n))
            or not np.array_equal(z['target'], z['audio'][2048:-2048])
            or not np.array_equal(z['target_source_coordinates'], z['source_coordinates'][2048:-2048])
            or z['fitted'].shape != (len(z['positions']), len(z['orders']), 2)
            or float(z['source_nominal_cutoff_Hz']) != 22000
            or int(z['native_rate_Hz']) != 48000 or len(z['source_filter_taps']) != 1025
            or any(not np.isfinite(z[k]).all() for k in required)):
        raise ValueError('C1 geometry, stereo, source filter, or finite values differ')
    clock = {k.removeprefix('clock_'):v for k,v in z.items() if k.startswith('clock_') and k != 'clock_times'}
    if not np.array_equal(evaluate(clock, z['phase_grid_indices']), z['source_coordinates']):
        raise ValueError('Capture does not carry the declared common C1 source clock')
    scalar = synthesize(z['fitted'], z['positions'], z['orders'], n)
    scale = max(float(np.max(abs(z['wave']))), 1e-300)
    error = float(np.max(abs(scalar-z['wave']))/scale)
    if error > 2e-11:
        raise ValueError('All-sample independent scalar OSC differs from saved fitted wave')
    return z, dict(schema=IDENTITY, label=label, known=known, inputs=inputs,
        scalar_OSC_all_samples=n, scalar_OSC_max_relative_peak_error=error,
        solver_mathematically_verified=True, legacy_fidelity_qualified=bool(info['fidelity_qualified']),
        native_source_fidelity_not_yet_qualified=True, eligible_for_later_source_statistics=False,
        fitted_timeline_is_diagnostic_only=True, no_runtime_or_hearing_promotion=True)
