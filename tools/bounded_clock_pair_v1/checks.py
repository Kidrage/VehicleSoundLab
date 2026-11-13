"""Independent coefficient and scalar finite-waveform checks."""
import math
import numpy as np
from .pair import design, solve


def check(model, initial, plan, rows, saved):
    tolerance = plan['rules']['maximum_forward_check_error']
    matrix = design(model, initial)
    reference = initial[:matrix.shape[1]]
    zero, zero_certificate = solve(matrix, saved['base_waveform'])
    zero_error = float(abs(zero-reference).max())
    assert zero_error <= tolerance
    rng = np.random.default_rng(623917)
    known = rng.normal(0, .025, matrix.shape[1])
    recovered, known_certificate = solve(matrix, matrix@known)
    known_error = float(abs(recovered-known).max())
    assert known_error <= tolerance
    independent, scalar = [], 0.
    m = model.original
    for row, key in zip(rows, ('minus', 'plus')):
        parameters = saved[key+'_parameters']
        local = design(model, parameters)
        alternative, _, rank, _ = np.linalg.lstsq(local, saved['base_waveform'], rcond=0.)
        assert rank == local.shape[1]
        error = float(abs(alternative-parameters[:2*m.parts]).max())
        assert error <= tolerance
        for index in (0, len(m.time)//2, len(m.time)-1):
            phase = float(math.fsum(float(x*y) for x, y in
                zip(m.phase_basis[index], parameters[2*m.parts:2*m.parts+m.phase_count])))
            start = 2*m.parts+m.phase_count
            beta = parameters[start:m.base_count].reshape(m.parts, m.envelope_count)
            terms = []
            for part, order in enumerate(m.orders):
                envelope = 1+math.fsum(float(x*y) for x, y in zip(m.envelope_basis[index], beta[part]))
                angle = 2*math.pi*order*(float(m.time[index])+phase)
                terms.append(envelope*(parameters[part]*math.cos(angle)+parameters[m.parts+part]*math.sin(angle)))
            actual = math.fsum(terms)
            scalar = max(scalar, abs(actual-saved[key+'_waveform'][index]))
        assert row['coefficient_certificate']['normalized_stationarity'] <= 1e-8
        assert row['feasible']
        assert abs(row['phase_difference_p95_cycles']-2*plan['rules']['maximum_point_phase_p95_cycles']) <= tolerance
        independent.append(dict(sign=row['sign'], independent_lstsq_coefficient_error=error, columns=int(rank)))
    assert scalar <= tolerance
    return dict(passed=True, zero_coefficient_error=zero_error, known_coefficient_error=known_error,
        zero_certificate=zero_certificate, known_certificate=known_certificate,
        scalar_waveform_maximum_error=scalar, independent_lstsq=independent,
        phase_estimator_qualified=False)
