"""Bind existing input/math/provenance, never prepare or fit another source."""
from contextlib import redirect_stdout
import io
from pathlib import Path
import sys
from c1_source_prepare_v1.provenance import Proofs
from research_archive_v1 import sha


def prerequisites(workspace, repo, report):
    p = Proofs(workspace, repo, report)
    base = workspace/'references/analysis'
    known_path = base/'c1_fit_registration_v1/known1/report.json'
    known = p.read(known_path)
    assert known['verification_passed'] and known['result'] == 'c1_fit_registration_known_verified'
    assert known['independent_success_pair_inspection'] and known['rejection_count'] == 18
    p.absorb(known)
    math_path = base/'c1_declared_objective_v1/real1/report.json'
    math = p.read(math_path)
    assert math['result'] == 'independent_c1_declared_real_preparation_verified'
    assert math['complete_declared_preparation_mathematics_passed']
    assert not math['original_SciPy_preparation_audit_passed']
    assert math['source_fidelity_not_evaluated'] and not math['eligible_for_later_source_statistics']
    p.absorb(math)
    parent = base/'c1_source_adapter_v1'
    prepared = p.read(parent/'prepare1/report.json')
    assert prepared['new_source_identity'] == 'vsl.c1-22k-source-preparation/1'
    failure_path = parent/'prepare_audit1/report.json'
    failure = p.read(failure_path)
    assert failure['result'] == 'failed' and '2.5585096571438003e-12' in failure['error']
    row, = prepared['cases']
    label = row['label']
    assert label == 'F3 Fifth First Late'
    packet = parent/'prepare1'/row['file']
    assert sha(p.bind(packet)) == row['sha256']
    for name in ('original_preparation', 'original_context'):
        assert Path(row[name]).stem == label
        p.bind(row[name])
    assert (row['frames'], row['target_frames'], row['nodes'], row['orders'], row['original_nodes']) == (18430, 14334, 73, 288, 57)
    # The original guard is valid only BEFORE the first new D registration.
    before = p.protect(label)
    assert before == p.read(parent/'prepare1/protected_before.json')
    return p, row, packet, before


def toolchain():
    import numpy as np
    import scipy
    stream = io.StringIO()
    with redirect_stdout(stream):
        np.show_config()
    files = {sys.executable, np.__file__, scipy.__file__}
    for package in (np, scipy):
        root = Path(package.__file__).parent
        files.update(str(p) for p in root.rglob('*.pyd'))
        for library in (root/'libs', root.parent/(root.name+'.libs')):
            if library.is_dir():
                files.update(str(p) for p in library.glob('*.dll'))
    return dict(python=sys.version, python_executable=sys.executable,
        numpy=np.__version__, scipy=scipy.__version__, numpy_configuration=stream.getvalue(),
        native_files_sha256={str(Path(p).resolve()):sha(p) for p in sorted(files)},
        native_file_hashes_are_identity_not_portable_runtime_bundle=True,
        thread_environment=dict(OPENBLAS_NUM_THREADS='2', OMP_NUM_THREADS='2', MKL_NUM_THREADS='2'))
