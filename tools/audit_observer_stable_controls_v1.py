"""Independent Decimal QR/reference defect identity on exact binary64 inputs."""
import argparse, os, shutil, sys
from decimal import Decimal, localcontext
from pathlib import Path
from research_archive_v1 import load, save, sha


def reference(z, precision):
    with localcontext() as ctx:
        ctx.prec = precision
        def matrix(x):
            return [[Decimal.from_float(float(v)) for v in row] for row in x]
        def vector(x):
            return [Decimal.from_float(float(v)) for v in x]
        def dot(x, y):
            return sum((a*b for a, b in zip(x, y)), Decimal(0))
        def transpose(x):
            return [list(v) for v in zip(*x)]
        def multiply(x, y):
            columns = transpose(y)
            return [[dot(row, col) for col in columns] for row in x]
        def mv(x, y):
            return [dot(row, y) for row in x]
        def minus(x, y):
            return [a-b for a, b in zip(x, y)]
        def norm(x):
            return dot(x, x).sqrt()
        A, U, V, H = (matrix(z[n]) for n in ('A', 'U', 'V', 'H'))
        b = vector(z['rhs'])
        beta = norm(b)
        target = [beta]+[Decimal(0)]*(len(H)-1)
        columns = transpose(H)
        Q, R = [], [[Decimal(0)]*len(columns) for _ in columns]
        for j, column in enumerate(columns):
            w = column.copy()
            for _ in range(2):
                for i, q in enumerate(Q):
                    c = dot(q, w)
                    R[i][j] += c
                    w = [v-c*t for v, t in zip(w, q)]
            R[j][j] = norm(w)
            if not R[j][j]:
                raise ArithmeticError('Rank-deficient Decimal control')
            Q.append([v/R[j][j] for v in w])
        qt = [dot(q, target) for q in Q]
        y = [Decimal(0)]*len(columns)
        for i in reversed(range(len(columns))):
            y[i] = (qt[i]-sum((R[i][j]*y[j] for j in range(i+1, len(columns))), Decimal(0)))/R[i][i]
        c = minus(mv(H, y), target)
        model_r = mv(U, c)
        model_g = mv(transpose(A), model_r)
        true_r = minus(mv(A, mv(V, y)), b)
        true_g = mv(transpose(A), true_r)
        AV, UH = multiply(A, V), multiply(U, H)
        E = [minus(x, y) for x, y in zip(AV, UH)]
        initial = minus(mv(U, target), b)
        defect = [x+y for x, y in zip(mv(E, y), initial)]
        gradient_defect = mv(transpose(A), defect)
        identity = norm(minus(minus(true_g, model_g), gradient_defect))
        bound = norm(sum(A, []))*(norm(sum(E, []))*norm(y)+norm(initial))
        actual = norm(minus(true_g, model_g))
        assert actual <= bound*(1+Decimal('1e-50'))+Decimal('1e-60')
        return dict(y=y, coefficients=c, model_r=model_r, model_g=model_g,
            original_normal_norm=norm(true_g), model_normal_norm=norm(model_g),
            projection_defect_bound=bound, normal_defect=actual, identity_error=identity)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('workspace', 'study', 'out'):
        p.add_argument('--'+name, type=Path, required=True)
    a = p.parse_args()
    sys.path.insert(0, str(a.workspace/'tools/python_deps'))
    import numpy as np
    a.out.mkdir(parents=True, exist_ok=False)
    shutil.copy2(__file__, a.out/'executed_audit.py')
    r = dict(result='running', cases=[])
    try:
        source = load(a.study/'report.json')
        assert source['result'] == 'observer_stable_controls_measured'
        assert [c['label'] for c in source['cases']] == ['rectangular', 'outside_gradient', 'cancellation',
            'ill_conditioned', 'exact_square', 'zero_rhs', 'projection_defect']
        for name, digest in source['sources'].items():
            assert sha(Path(__file__).resolve().parents[1]/name) == sha(a.study/'exact_sources'/name) == digest
        for case in source['cases']:
            path = a.study/case['file']
            assert sha(path) == case['sha256']
            with np.load(path) as z:
                q80, q110 = reference(z, 80), reference(z, 110)
                maximum_precision_error = 0.
                for field in ('y', 'coefficients', 'model_r', 'model_g'):
                    precision = max((abs(x-y)/max(Decimal(1), abs(y)) for x, y in zip(q80[field], q110[field])), default=Decimal(0))
                    assert precision < Decimal('1e-50')
                    maximum_precision_error = max(maximum_precision_error, float(precision))
                assert q110['identity_error'] < Decimal('1e-85')*max(Decimal(1), q110['original_normal_norm'])
                c = np.array([float(v) for v in q110['coefficients']])
                mr = np.array([float(v) for v in q110['model_r']])
                mg = np.array([float(v) for v in q110['model_g']])
                # Backward QR error scales with ||b||; gradient products additionally
                # scale with ||A||. This checks the estimator, not exact full convergence.
                c_error = float(np.linalg.norm(z['residual_coefficients']-c)/max(1., np.linalg.norm(z['rhs'])))
                r_error = float(np.linalg.norm(z['stable_residual']-mr)/max(1., np.linalg.norm(z['rhs'])))
                g_error = float(np.linalg.norm(z['stable_normal']-mg)/max(1., np.linalg.norm(z['A'])*np.linalg.norm(z['rhs'])))
                assert max(c_error, r_error, g_error) < 2e-12
                direct_r = z['A']@z['z']-z['rhs']
                direct_g = z['A'].T@direct_r
                assert np.array_equal(direct_r, z['direct_residual'])
                assert np.array_equal(direct_g, z['direct_normal'])
                info = case['info']
                assert abs(np.linalg.norm(z['stable_normal'])-info['stable_normal_norm']) < 1e-12
                if case['label'] == 'outside_gradient':
                    assert info['projected_only_normal_norm'] < 1e-12
                    assert abs(info['outside_subspace_normal_norm']-3.) < 1e-12
                    assert info['stable_normal_relative'] > 1.
                if case['label'] == 'projection_defect':
                    assert info['relative_backward_discrepancy'] > 1e-3
                r['cases'].append(dict(label=case['label'], independent_precision_digits=[80, 110],
                    maximum_precision_difference=maximum_precision_error, coefficient_relative_error=c_error,
                    residual_relative_error=r_error, normal_scaled_error=g_error,
                    original_high_precision_normal_norm=str(q110['original_normal_norm']),
                    projected_high_precision_normal_norm=str(q110['model_normal_norm']),
                    projection_gradient_defect_bound=str(q110['projection_defect_bound']),
                    actual_gradient_defect=str(q110['normal_defect']), identity_error=str(q110['identity_error'])))
                print('DECIMAL AUDIT', case['label'], c_error, r_error, g_error, flush=True)
        r.update(result='independent_observer_stable_controls_passed', controls=7,
            outside_subspace_and_projection_defect_controls_verified=True,
            producer_sha256=sha(a.study/'report.json'), auditor_sha256=sha(__file__))
        save(a.out/'report.json', r)
    except BaseException as error:
        r.update(result='failed', error=repr(error))
        save(a.out/'report.json', r)
        raise


if __name__ == '__main__':
    main()
