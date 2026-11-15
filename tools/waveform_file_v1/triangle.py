"""Complete block upper-triangular solves; off-diagonal blocks all participate."""
import numpy as np
from scipy import linalg


def solve(factor, value, transpose=False):
    matrix = factor.raw
    k, block = factor.k, factor.block
    if factor.columns != k:
        raise ValueError('Square upper factor of a tall QR required')
    value = np.asarray(value, dtype='float64')
    vector = value.ndim == 1
    if (value.ndim not in (1, 2) or value.shape[0] != k
            or not np.isfinite(value).all()):
        raise ValueError('Finite complete triangular RHS required')
    if not vector and value.shape[1] > block:
        result = np.column_stack([solve(factor, value[:, j:j+block], transpose)
                                  for j in range(0, value.shape[1], block)])
        factor.ledger.add('fileTriangle.batched_complete_rhs_result', result)
        return result
    result = np.array(value[:, None] if vector else value, order='F', copy=True)
    factor.ledger.add('fileTriangle.complete_rhs', result)
    starts = list(range(0, k, block))
    for first in (starts if transpose else reversed(starts)):
        last = min(first+block, k)
        diagonal = matrix.read(first, last, first, last)
        rhs = np.array(result[first:last], order='F', copy=True)
        factor.ledger.add('fileTriangle.diagonal_rhs', rhs)
        answer = linalg.solve_triangular(diagonal, rhs, trans='T' if transpose else 'N',
                                         lower=False, overwrite_b=True, check_finite=False)
        if not np.shares_memory(answer, rhs):
            raise ArithmeticError('Block triangular kernel unexpectedly copied its owned RHS')
        factor.calls.append(factor._call('trtrs_T' if transpose else 'trtrs_N',
                                        diagonal, rhs, 0, True))
        factor.ledger.add('fileTriangle.diagonal_result', answer)
        factor.ledger.snapshot('fileTriangle.diagonal.solved')
        result[first:last] = answer
        for other in (range(last, k, block) if transpose else range(0, first, block)):
            stop = min(other+block, k)
            panel = (matrix.read(first, last, other, stop) if transpose
                     else matrix.read(other, stop, first, last))
            update = (panel.T if transpose else panel) @ answer
            factor.ledger.add('fileTriangle.offdiagonal_product', update)
            result[other:stop] -= update
            factor.ledger.snapshot('fileTriangle.offdiagonal.updated')
            del panel, update
    return result[:, 0] if vector else result
