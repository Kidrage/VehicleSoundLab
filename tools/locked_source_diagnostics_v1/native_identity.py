"""Independent changed-source/native identity; no producer binding imports."""
from pathlib import Path
import numpy as np
from research_archive_v1 import load, sha


def verify(source, study, repo, inputs):
    def read(path):
        path = Path(path)
        inputs[str(path)] = sha(path)
        return load(path)

    for name, digest in source['sources'].items():
        assert sha(repo / name) == sha(study / 'exact_sources' / name) == digest
    for name, digest in source['inputs'].items():
        assert sha(name) == digest, name
        inputs[name] = digest
    paths = {name: Path(value) for name, value in source['paths'].items()}
    case = paths['case']
    info = read(case / 'report.json')
    proof = read(paths['math_audit'])
    assert proof['result'] == 'independent_locked_source_real_verified' and proof['verification_passed']
    assert info['result'] == 'locked_source_real_case_measured'
    row = proof['case']
    assert row['verification_passed'] and row['producer_sha256'] == sha(case / 'report.json')
    assert row['capture_sha256'] == info['capture_sha256'] == sha(case / 'capture.npz')
    for field in ('solver_qualified', 'fidelity_qualified'):
        assert row[field] == info[field] == source['source'][field]
        assert info[field] == source['source_' + field]
    assert source['source']['case_report_sha256'] == sha(case / 'report.json')
    assert source['source']['capture_sha256'] == row['capture_sha256']
    assert source['source']['math_audit_sha256'] == sha(paths['math_audit'])
    spec_path = case.parent / 'run_spec.json'
    spec = read(spec_path)
    assert proof['inputs'][str(spec_path)] == sha(spec_path) == source['source']['binding_sha256']
    assert Path(source['source']['binding_file']).resolve() == spec_path.resolve()
    assert spec['schema'] == 'vsl.locked_source_real_spec/1' and spec['only_one_finite_case']
    assert spec['declared_cases'] == [case.name] and case.name != 'F3 Fifth First Early'
    assert case.name in spec['declared_cases'] and case.name == source['label']
    for name, digest in spec['sources'].items():
        assert sha(repo / name) == sha(case.parent / 'exact_sources' / name) == digest
    for name, digest in spec['inputs'].items():
        assert sha(name) == digest
    with np.load(case / 'capture.npz') as f:
        z = {key: f[key] for key in f.files}
    assert np.array_equal(z['orders'], np.arange(1, 289))
    assert np.array_equal(z['audio'][2048:-2048], z['target'])
    assert z['fitted'].shape == (len(z['positions']), 288, 2) and np.isfinite(z['fitted']).all()
    known = read(paths['known_study'] / 'report.json')
    ka = read(paths['known_audit'] / 'report.json')
    assert known['result'] == 'native_clock_render_known_measured'
    assert ka['result'] == 'independent_native_clock_render_known_verified' and ka['all_known_qualified']
    assert len(ka['cases']) == 13 and all(c['all_known_gates_passed'] for c in ka['cases'])
    assert ka['producer_sha256'] == sha(paths['known_study'] / 'report.json')
    for name, digest in known['sources'].items():
        if name.startswith('tools/native_clock_render_v1/'):
            assert sha(repo / name) == sha(paths['known_study'] / 'exact_sources' / name) == digest
    prep = read(paths['native_study'] / 'report.json')
    pa = read(paths['native_audit'] / 'report.json')
    assert prep['result'] == 'native_clock_six_real_intervals_prepared' and len(prep['cases']) == 6
    assert pa['result'] == 'independent_native_clock_real_preparation_verified'
    assert pa['all_preparation_qualified'] and len(pa['cases']) == 6
    assert pa['producer_sha256'] == sha(paths['native_study'] / 'report.json')
    native_row = next(c for c in prep['cases'] if c['label'] == case.name)
    assert native_row == source['native_preparation']
    assert next(c for c in pa['cases'] if c['label'] == case.name)['all_preparation_checks_passed']
    native_file = paths['native_study'] / native_row['file']
    assert sha(native_file) == native_row['sha256']
    assert sha(native_row['original_preparation']) == native_row['original_preparation_sha256']
    assert sha(info['prepared_file']) == info['prepared_sha256']
    new_preparation = read(Path(info['prepared_file']).parent/'report.json')
    assert new_preparation['result'] == 'locked_source_five_prepared'
    new_row = next(c for c in new_preparation['cases'] if c['label'] == case.name)
    assert new_row == source['new_method_preparation']
    assert new_row['sha256'] == info['prepared_sha256'] and new_row['file'] == Path(info['prepared_file']).name
    assert Path(new_row['original_preparation']).resolve() == Path(native_row['original_preparation']).resolve()
    with np.load(info['prepared_file']) as prepared:
        for name in prepared.files: assert np.array_equal(prepared[name], z[name]), name
    query_file = Path(new_row['source_query_file'])
    assert new_preparation['inputs'][str(query_file)] == sha(query_file)
    inputs[str(query_file)] = sha(query_file)
    with np.load(query_file) as query: assert np.array_equal(z['audio'], query['sinc128'])
    with np.load(native_file) as f:
        native = {key: f[key] for key in f.files}
    with np.load(native_row['original_preparation']) as f:
        original = {key: f[key] for key in f.files}
    for name in ('source_coordinates', 'target_source_coordinates', 'positions', 'original_positions', 'orders'):
        assert np.array_equal(z[name], original[name]) and np.array_equal(z[name], native[name]), name
    for name in ('native', 'source_start', 'scale', 'weights', 'band_power', 'floor_active', 'sigma', 'amplitude'):
        assert np.array_equal(z[name], original[name]), name
    assert np.array_equal(z['metric_target'], original['target'])
    first, stop = int(native['first']), int(native['stop'])
    assert first == native_row['native_first'] and stop == native_row['native_stop']
    assert np.array_equal(native['raw_native_target'], z['native'][first:stop])
    assert float(native['native_start']) == float(z['source_start']) + first / 48000
    assert float(native['registered_start']) == float(z['source_start'])
    assert source['meter_protocol']['protocol'] == 'independent_extraction_sound_composition_verified'
    assert not source['meter_protocol']['legacy_cross_operator_all_statistics_qualified']
    assert source['meter_protocol']['retained_legacy_normalized_failure_count'] == 5
    assert not source['meter_protocol']['sensitivity_is_certified']
    return z, native
