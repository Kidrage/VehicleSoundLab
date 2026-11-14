"""Independent Fraction arithmetic audit, without importing the integer kernels."""
import argparse
from fractions import Fraction as Q
import os
from pathlib import Path
import shutil
import sys

p = argparse.ArgumentParser(description=__doc__)
for key in ('workspace', 'controls', 'replay', 'out'):
    p.add_argument('--'+key, type=Path, required=True)
a = p.parse_args()
repo = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(a.workspace/'tools/python_deps'))
for key in ('OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS', 'OMP_NUM_THREADS'):
    os.environ[key] = '2'
import numpy as np
from research_archive_v1 import load, save, sha

a.out.mkdir(parents=True, exist_ok=False)
r = dict(result='running', sources={}, inputs={}, controls=[], source_cases=[])
floor, cap = Q.from_float(1e-30), Q.from_float(.95)


def rational(array):
    return [[Q.from_float(float(x)) for x in row] for row in array]


def moments(array):
    previous, following = array[:-1], array[1:]
    n = sum((x*y for row, nxt in zip(previous, following) for x, y in zip(row, nxt)), Q())
    d = sum((x*x for row in previous for x in row), Q())
    raw = n/max(d, floor)
    return n, d, max(-cap, min(cap, raw))


def check_bound(array, other, stored):
    n, d, qa = moments(array)
    nb, db, qb = moments(other)
    e = max(abs(x-y) for row, nxt in zip(array, other) for x, y in zip(row, nxt))
    prev = sum((abs(x) for row in array[:-1] for x in row), Q())
    nxt = sum((abs(x) for row in array[1:] for x in row), Q())
    m = (len(array)-1)*len(array[0])
    dn, dd = e*(prev+nxt)+m*e*e, 2*e*prev+m*e*e
    assert abs(nb-n) <= dn and abs(db-d) <= dd
    bound = min(2*cap, (dn+abs(n/max(d, floor))*dd)/max(floor, d-dd))
    assert abs(qa-qb) <= bound
    for key, value in [('exact_first', qa), ('exact_second', qb),
                       ('exact_quotient_difference', abs(qa-qb)), ('perturbation_bound', bound),
                       ('maximum_residual_difference_FS', e), ('first_denominator_FS2', d),
                       ('numerator_difference_FS2', abs(nb-n)), ('denominator_difference_FS2', abs(db-d))]:
        assert float(value) == stored[key], key
    return float(abs(qa-qb)), float(bound)


def consume(path):
    r['inputs'][str(path)] = sha(path)
    return path


try:
    for name in ('tools/audit_residual_ratio_numeric_v1.py', 'tools/research_archive_v1.py'):
        dest = a.out/'exact_sources'/name
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(repo/name, dest)
        r['sources'][name] = sha(repo/name)
    controls = load(consume(a.controls/'report.json'))
    replay = load(consume(a.replay/'report.json'))
    assert controls['result'] == 'known_exact_moment_and_perturbation_controls_passed'
    assert replay['result'] == 'frozen_models_replay_exact_and_literal_rho_moments_verified'
    for report, folder in [(controls, a.controls), (replay, a.replay)]:
        for name, digest in report['sources'].items():
            assert sha(repo/name) == digest == sha(folder/'exact_sources'/name)
    # Independently exercise floor/clipping before any frozen real-array access.
    fixtures = dict(zero=np.zeros((64, 4)), below_floor=np.tile(np.arange(64)[:, None]*1e-20, (1, 4)),
                    positive_clip=np.tile(1.001**np.arange(64)[:, None], (1, 4)),
                    negative_clip=np.tile((-1.001)**np.arange(64)[:, None], (1, 4)))
    for item in controls['primitives']:
        _, _, q = moments(rational(fixtures[item['name']]))
        if item['name'] == 'zero':
            assert q == 0
        if item['name'] == 'positive_clip':
            assert q == cap
        if item['name'] == 'negative_clip':
            assert q == -cap
        assert abs(float(q)-float(np.clip(item['raw_ratio'], -.95, .95))) < 5e-15
    for item in controls['cases']:
        with np.load(consume(a.controls/(item['name']+'.npz'))) as f:
            actual, other, literal = f['actual_residual'], f['alternative_residual'], f['literal_rho']
        for h, stored in enumerate(item['harmonics']):
            values, alternative = rational(actual[:, h]), rational(other[:, h])
            _, _, q = moments(values)
            assert abs(float(q)-literal[h]) < 5e-15
            check_bound(values, alternative, stored)
        r['controls'].append(dict(name=item['name'], harmonics_checked=8))
    for item in replay['cases']:
        folder = a.replay/item['name']
        with np.load(consume(folder/'residual_trace.npz')) as f:
            arrays = {k: f[k] for k in f.files}
        assert sha(consume(folder/'replayed.model')) == item['original_model_sha256']
        lines = (folder/'replayed.model').read_text(encoding='ascii').splitlines()
        header = lines[0].split()
        hcount, k = int(header[5]), int(header[6])
        literal = np.array([float(line.split()[4+4*k]) for line in lines[2:]])
        assert np.array_equal(literal, arrays['literal_rho'])
        max_error = max_difference = max_bound = 0.
        variants = ('same_FFT_projection', 'original_direct_projection', 'modulo_direct_projection')
        for h in range(hcount):
            actual = rational(arrays['actual_residual'][:, h])
            _, _, q = moments(actual)
            max_error = max(max_error, abs(float(q)-literal[h]))
            assert abs(float(q)-literal[h]) < 5e-15
            for name in variants:
                difference, bound = check_bound(actual, rational(arrays[name][:, h]), item['harmonics'][h]['alternatives'][name])
                max_difference, max_bound = max(max_difference, difference), max(max_bound, bound)
        r['source_cases'].append(dict(name=item['name'], exact_harmonics=hcount,
                                      maximum_literal_error=max_error, conditional_pairs=hcount*3,
                                      maximum_difference=max_difference, maximum_bound=max_bound))
        save(a.out/'report.json', r)
    for name, digest in replay['inputs'].items():
        assert sha(consume(Path(name))) == digest
    r.update(result='independent_fraction_moments_and_conditional_bounds_verified',
             known_harmonics=64, primitive_cases=4, source_harmonics=576, source_conditional_pairs=1728,
             original_projection_gate_still_failed=True, all_original_parameter_audits_passed=False,
             independent_SVD=False, live_profile_promoted=False, new_audio=False)
except Exception as exc:
    r.update(result='failed', error=repr(exc))
    raise
finally:
    save(a.out/'report.json', r)
print(dict(result=r['result'], sources=r['source_cases']))
