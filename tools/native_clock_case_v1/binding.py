"""Bind audited real fits to separately qualified native reference intervals."""
from pathlib import Path
import numpy as np
from research_archive_v1 import load, sha
from extraction_sound_v1.consume import terminal, qualification


def bind(case, math_audit, *, repo, workspace, native_study, native_audit,
         known_study, known_audit):
    case, repo, workspace, native_study, native_audit, known_study, known_audit = map(
        Path, (case, repo, workspace, native_study, native_audit, known_study, known_audit))
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
    row = next((c for c in prepared['cases'] if c['label'] == case.name), None)
    audit_row = next((c for c in proof['cases'] if c['label'] == case.name), None)
    if row is None or audit_row is None or not audit_row['all_preparation_checks_passed']:
        raise ValueError('Actual case missing from independently audited native preparation')
    z, binding = terminal(case, math_audit, repo=repo, known=False)
    for path in (case / 'report.json', case / 'capture.npz', Path(math_audit), Path(binding['binding_file'])):
        inputs[str(path)] = sha(path)
    native_file = native_study / row['file']
    if sha(native_file) != row['sha256'] or sha(row['original_preparation']) != row['original_preparation_sha256']:
        raise ValueError('Actual native or original preparation changed')
    inputs[str(native_file)] = row['sha256']
    inputs[row['original_preparation']] = row['original_preparation_sha256']
    with np.load(native_file) as f:
        native = {name: f[name] for name in f.files}
    with np.load(row['original_preparation']) as f:
        original = {name: f[name] for name in f.files}
    info = load(case / 'report.json')
    if (Path(info['prepared_file']).resolve() != Path(row['original_preparation']).resolve()
            or info['prepared_sha256'] != row['original_preparation_sha256']):
        raise ValueError('Fit and native preparation refer to different original data')
    for name in ('source_coordinates', 'target_source_coordinates', 'positions',
                 'original_positions', 'orders'):
        if not (np.array_equal(z[name], original[name]) and np.array_equal(z[name], native[name])):
            raise ValueError('Native/fit/original geometry differs: ' + name)
    for name in ('native', 'source_start', 'scale', 'audio', 'target'):
        if not np.array_equal(z[name], original[name]):
            raise ValueError('Original recording, scales or target differs: ' + name)
    if (z['fitted'].shape != (len(z['positions']), 288, 2)
            or not np.isfinite(z['fitted']).all()
            or not np.array_equal(z['orders'], np.arange(1, 289))):
        raise ValueError('Finite complete288-order stereo fitted coefficients required')
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
    return z, native, dict(source=binding, native_preparation=row,
                          meter_protocol=protocol, inputs=inputs)
