"""Exact binary-rational moments and finite-perturbation quotient bounds.

No FFT, SVD, sound profile or source assumptions. All products and summations
use integer arithmetic after placing binary64 entries on a common dyadic grid.
"""
from fractions import Fraction
import numpy as np


FLOOR = Fraction.from_float(1e-30)
CAP = Fraction.from_float(.95)


def dyadic(*arrays):
    inputs = [np.asarray(a, dtype='float64') for a in arrays]
    assert all(np.isfinite(a).all() for a in inputs)
    pairs = [[float(x).as_integer_ratio() for x in a.ravel()] for a in inputs]
    exponent = max(d.bit_length()-1 for row in pairs for _, d in row)
    result = []
    for row, array in zip(pairs, inputs):
        result.append(np.array([n << (exponent-(d.bit_length()-1)) for n, d in row],
                               dtype=object).reshape(array.shape))
    return result, exponent


def products(values):
    first, second = values[:-1].ravel(), values[1:].ravel()
    return sum(x*y for x, y in zip(first, second)), sum(x*x for x in first)


def clipped(numerator, denominator, exponent):
    denominator = max(Fraction(denominator), FLOOR*(1 << (2*exponent)))
    raw = Fraction(numerator)/denominator
    return max(-CAP, min(CAP, raw)), raw


def exact_rho(residual):
    (values,), exponent = dyadic(residual)
    numerator, denominator = products(values)
    rho, raw = clipped(numerator, denominator, exponent)
    return float(rho), dict(numerator_FS2=float(Fraction(numerator, 1 << (2*exponent))),
                            denominator_FS2=float(Fraction(denominator, 1 << (2*exponent))),
                            raw_ratio=float(raw), used_floor=denominator < FLOOR*(1 << (2*exponent)))


def compare(first, second):
    assert np.shape(first) == np.shape(second) and np.ndim(first) == 2
    (a, b), exponent = dyadic(first, second)
    n, d = products(a)
    nb, db = products(b)
    qa, rawa = clipped(n, d, exponent)
    qb, rawb = clipped(nb, db, exponent)
    epsilon = max(abs(x-y) for x, y in zip(a.ravel(), b.ravel()))
    previous, following = a[:-1].ravel(), a[1:].ravel()
    m = len(previous)
    delta_n = epsilon*(sum(abs(v) for v in previous)+sum(abs(v) for v in following))+m*epsilon**2
    delta_d = 2*epsilon*sum(abs(v) for v in previous)+m*epsilon**2
    assert abs(nb-n) <= delta_n and abs(db-d) <= delta_d
    floor = FLOOR*(1 << (2*exponent))
    bound = (delta_n+abs(rawa)*delta_d)/max(floor, d-delta_d)
    bound = min(2*CAP, bound)
    difference = abs(qa-qb)
    assert difference <= bound
    return dict(exact_first=float(qa), exact_second=float(qb),
                exact_quotient_difference=float(difference), perturbation_bound=float(bound),
                maximum_residual_difference_FS=float(Fraction(epsilon, 1 << exponent)),
                numerator_difference_FS2=float(Fraction(abs(nb-n), 1 << (2*exponent))),
                denominator_difference_FS2=float(Fraction(abs(db-d), 1 << (2*exponent))),
                first_denominator_FS2=float(Fraction(d, 1 << (2*exponent))),
                bound_exactly_contains_difference=True)
