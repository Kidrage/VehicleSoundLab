"""Finite-marginal conditional circular-moment feasibility; not source separation."""
import numpy as np
from scipy.optimize import linprog
from scipy.sparse import coo_matrix, hstack, vstack, csr_matrix


def hats(values, knots):
    if len(knots) == 1:
        return np.ones((len(values), 1))
    left = np.clip(np.searchsorted(knots, values, side='right')-1, 0, len(knots)-2)
    u = np.clip((values-knots[left])/(knots[left+1]-knots[left]), 0, 1)
    output = np.zeros((len(values), len(knots)))
    output[np.arange(len(values)), left] = 1-u
    output[np.arange(len(values)), left+1] = u
    return output


def amplitude_grid(product, count):
    mean = product.mean()
    if not np.isfinite(product).all() or mean <= 0 or np.min(product) < 0:
        raise ValueError('Positive finite amplitude-product mean is required')
    normalized = product/mean
    knots = np.unique(np.quantile(normalized, np.linspace(0, 1, count)))
    weights = hats(normalized, knots)
    masses = weights.mean(axis=0)
    assert np.all(masses > 0)
    conditional = np.mean(weights*normalized[:, None], axis=0)/masses
    return dict(mean=mean, knots=knots, masses=masses, product=conditional)


def phase_cells(table):
    n = len(table)
    low = np.r_[table[0], table[:-1], table[-1]]
    high = np.r_[table[0], table[1:], table[-1]]
    masses = np.r_[.5, np.ones(n-1), .5]/n
    moments = np.exp(.5j*(low+high))*np.sinc((high-low)/(2*np.pi))
    return dict(low=low, high=high, masses=masses, moments=moments)


def project(product, row_mass, phase_moment, column_mass, target, tolerance=1e-9):
    """Closest normalized complex moment in L-infinity, with LP certificates."""
    rows, columns = len(product), len(phase_moment)
    variables = rows*columns
    index = np.arange(variables).reshape(rows, columns)
    rr = coo_matrix((np.ones(variables), (np.repeat(np.arange(rows), columns), index.ravel())),
                    shape=(rows, variables)).tocsr()
    cc = coo_matrix((np.ones(variables), (np.tile(np.arange(columns), rows), index.ravel())),
                    shape=(columns, variables)).tocsr()
    eq = hstack([vstack([rr, cc[:-1]]), csr_matrix((rows+columns-1, 1))]).tocsr()
    rhs = np.r_[row_mass, column_mass[:-1]]
    cross = product[:, None]*phase_moment[None, :]
    matrix = np.stack([cross.real.ravel(), -cross.real.ravel(),
                       cross.imag.ravel(), -cross.imag.ravel()])
    ub = hstack([csr_matrix(matrix), csr_matrix(-np.ones((4, 1)))]).tocsr()
    bound = np.array([target.real, -target.real, target.imag, -target.imag])
    objective = np.r_[np.zeros(variables), 1.]
    result = linprog(objective, A_ub=ub, b_ub=bound, A_eq=eq, b_eq=rhs,
                     bounds=(0, None), method='highs', options={
                         'primal_feasibility_tolerance': tolerance,
                         'dual_feasibility_tolerance': tolerance})
    if not result.success:
        raise RuntimeError(f'LP status{result.status}: {result.message}')
    coupling = result.x[:-1].reshape(rows, columns)
    actual = np.sum(coupling*cross)
    y, lam = result.eqlin.marginals, result.ineqlin.marginals
    reduced = objective-eq.T@y-ub.T@lam
    return dict(coupling=coupling, tau=float(result.x[-1]),
                actual=actual, equality_dual=y, inequality_dual=lam,
                lower_dual=result.lower.marginals,
                primal_row_error=float(abs(coupling.sum(axis=1)-row_mass).max()),
                primal_column_error=float(abs(coupling.sum(axis=0)-column_mass).max()),
                dual_feasibility_error=float(max(0, -reduced.min(), lam.max())),
                stationarity_error=float(abs(reduced-result.lower.marginals).max()),
                primal_dual_gap=float(result.fun-(rhs@y+bound@lam)),
                actual_error_Linf=float(max(abs((actual-target).real), abs((actual-target).imag))))
