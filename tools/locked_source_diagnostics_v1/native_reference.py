"""Fit-independent bridge from changed-source preparation to original native references."""
from pathlib import Path
import numpy as np
from research_archive_v1 import load, sha
from extraction_sound_v1.consume import qualification


def bind_reference(z, label, prepared_file, prepared_sha256, *, repo, workspace,
                   native_study, native_audit, known_study, known_audit):
    prepared_file, repo, workspace, native_study, native_audit, known_study, known_audit = map(
        Path, (prepared_file, repo, workspace, native_study, native_audit, known_study, known_audit))
    inputs = {}

    def read(path):
        path = Path(path)
        inputs[str(path)] = sha(path)
        return load(path)

    known = read(known_study / 'report.json')
    proof = read(known_audit / 'report.json')
    if not (known.get('result') == 'native_clock_render_known_measured'
            and proof.get('result') == 'independent_native_clock_render_known_verified'
            and proof.get('all_known_qualified') and len(proof.get('cases', [])) == 13
            and proof['producer_sha256'] == inputs[str(known_study / 'report.json')]):
        raise ValueError('Complete independent native renderer qualification required')
    for name, digest in known['sources'].items():
        if name.startswith('tools/native_clock_render_v1/'):
            if sha(repo / name) != digest or sha(known_study / 'exact_sources' / name) != digest:
                raise ValueError('Qualified native renderer changed: ' + name)
    prepared = read(native_study / 'report.json')
    proof = read(native_audit / 'report.json')
    if not (prepared.get('result') == 'native_clock_six_real_intervals_prepared'
            and len(prepared.get('cases', [])) == 6
            and proof.get('result') == 'independent_native_clock_real_preparation_verified'
            and proof.get('all_preparation_qualified') and len(proof.get('cases', [])) == 6
            and proof['producer_sha256'] == inputs[str(native_study / 'report.json')]):
        raise ValueError('Exact independently audited six-case native preparation required')
    for name, digest in prepared['inputs'].items():
        if sha(name) != digest:
            raise ValueError('Native preparation input changed: ' + name)
        inputs[name] = digest
    row = next((c for c in prepared['cases'] if c['label'] == label), None)
    audit_row = next((c for c in proof['cases'] if c['label'] == label), None)
    if row is None or audit_row is None or not audit_row['all_preparation_checks_passed']:
        raise ValueError('Actual case missing from independently audited native preparation')
    if sha(prepared_file) != prepared_sha256:
        raise ValueError('Explicit new preparation differs from supplied digest')
    inputs[str(prepared_file)] = prepared_sha256
    native_file = native_study / row['file']
    if sha(native_file) != row['sha256'] or sha(row['original_preparation']) != row['original_preparation_sha256']:
        raise ValueError('Actual native or original preparation changed')
    inputs[str(native_file)] = row['sha256']
    inputs[row['original_preparation']] = row['original_preparation_sha256']
    with np.load(native_file) as f:
        native = {name: f[name] for name in f.files}
    with np.load(row['original_preparation']) as f:
        original = {name: f[name] for name in f.files}
    info = dict(prepared_file=str(prepared_file), prepared_sha256=prepared_sha256)
    new_preparation = read(Path(info['prepared_file']).parent/'report.json')
    if new_preparation.get('result') != 'locked_source_five_prepared':
        raise ValueError('Explicit changed-source preparation required')
    new_row = next((c for c in new_preparation['cases'] if c['label'] == label), None)
    if (new_row is None or new_row['sha256'] != info['prepared_sha256']
            or new_row['file'] != Path(info['prepared_file']).name
            or Path(new_row['original_preparation']).resolve() != Path(row['original_preparation']).resolve()):
        raise ValueError('Changed-source and native preparation refer to different original data')
    query_file = Path(new_row['source_query_file'])
    if new_preparation['inputs'].get(str(query_file)) != sha(query_file):
        raise ValueError('Audited sinc128 query data changed')
    inputs[str(query_file)] = sha(query_file)
    with np.load(query_file) as saved:
        if not np.array_equal(z['audio'], saved['sinc128']):
            raise ValueError('New fitted audio differs from audited sinc128 source')
    if not np.array_equal(z['metric_target'], original['target']):
        raise ValueError('Explicit calibration differs from original legacy target')
    for name in ('source_coordinates', 'target_source_coordinates', 'positions',
                 'original_positions', 'orders'):
        if not (np.array_equal(z[name], original[name]) and np.array_equal(z[name], native[name])):
            raise ValueError('Native/fit/original geometry differs: ' + name)
    for name in ('native', 'source_start', 'scale', 'weights', 'band_power', 'floor_active', 'sigma', 'amplitude'):
        if not np.array_equal(z[name], original[name]):
            raise ValueError('Original recording or legacy calibration differs: ' + name)
    if not np.array_equal(z['orders'], np.arange(1, 289)):
        raise ValueError('Every original288order required for physical reference bridge')
    first, stop = int(native['first']), int(native['stop'])
    if (first != row['native_first'] or stop != row['native_stop']
            or not np.array_equal(native['raw_native_target'], z['native'][first:stop])
            or float(native['native_start']) != float(z['source_start']) + first / 48000
            or float(native['registered_start']) != float(z['source_start'])):
        raise ValueError('Native source registration changed')
    meter_root = workspace / 'references/analysis/extraction_sound_v1'
    protocol = qualification(repo, meter_root / 'known2', meter_root / 'known_composed_audit1')
    for folder in ('known2', 'known_composed_audit1'):
        read(meter_root / folder / 'report.json')
    return native, dict(native_preparation=row, new_method_preparation=new_row,
                          meter_protocol=protocol, inputs=inputs)
