"""Bitwise compare all twelve RAM/mapped captures and actual trimmed raw bases."""
import argparse, shutil, sys
from pathlib import Path
import hashlib
from research_archive_v1 import load, save, sha


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('workspace', 'ram', 'mapped', 'out'):
        p.add_argument('--'+name, type=Path, required=True)
    a = p.parse_args()
    sys.path.insert(0, str(a.workspace/'tools/python_deps'))
    import numpy as np
    a.out.mkdir(parents=True, exist_ok=False)
    shutil.copy2(__file__, a.out/'executed_audit.py')
    left, right = load(a.ram/'report.json'), load(a.mapped/'report.json')
    assert left['all_qualified'] and right['all_qualified'] and len(left['cases']) == len(right['cases']) == 12
    result = dict(result='running', cases=[])
    for l, r in zip(left['cases'], right['cases']):
        assert (l['kind'], l['label']) == (r['kind'], r['label'])
        assert sha(a.ram/l['file']) == l['sha256'] and sha(a.mapped/r['file']) == r['sha256']
        values = {}
        with np.load(a.ram/l['file']) as x, np.load(a.mapped/r['file']) as y:
            assert set(x.files) == set(y.files)
            for name in x.files:
                first, second = x[name], y[name]
                assert first.shape == second.shape and first.dtype == second.dtype
                d1 = hashlib.sha256(np.ascontiguousarray(first).view('uint8')).hexdigest()
                d2 = hashlib.sha256(np.ascontiguousarray(second).view('uint8')).hexdigest()
                assert d1 == d2, (r['label'], name)
                values[name] = d1
            basis = Path(r['solver']['basis_directory']).resolve()
            assert basis.is_relative_to(a.mapped.resolve())
            for name in ('U', 'V'):
                shape = tuple(r['solver']['basis_shapes'][name])
                path = basis/(name+'.bin')
                assert path.stat().st_size == int(np.prod(shape))*8
                raw = np.memmap(path, mode='r', dtype='float64', shape=shape, order='F')
                assert hashlib.sha256(np.ascontiguousarray(raw).view('uint8')).hexdigest() == values[name]
        result['cases'].append(dict(kind=r['kind'], label=r['label'], arrays_sha256=values,
            raw_basis_files_sha256={str((basis/(name+'.bin')).relative_to(a.mapped)):sha(basis/(name+'.bin')) for name in ('U', 'V')}))
        print('STORAGE EXACT', r['kind'], r['label'], len(values), flush=True)
    result.update(result='independent_observer_stable_storage_passed', all12_arrays_bitwise_exact=True,
        all24_trimmed_raw_bases_verified=True, RAM_report_sha256=sha(a.ram/'report.json'),
        mapped_report_sha256=sha(a.mapped/'report.json'), auditor_sha256=sha(__file__))
    save(a.out/'report.json', result)


if __name__ == '__main__':
    main()
