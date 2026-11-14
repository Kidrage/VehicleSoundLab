"""Independent dynamic clock, Fourier alignment extrema, and sparse direct sums."""
import math
import numpy as np
from scipy import optimize
from sustain_osc_v1.oracle import Gaussian


def clock(events, frames):
    roots = np.empty(frames)
    phases = np.empty(frames)
    root, phase, target, event = events[0, 1], 0., events[0, 1], 1
    follow = 1-math.exp(-1/(.018*48000))
    for n in range(frames):
        if event < len(events) and n == events[event, 0]:
            target = events[event, 1]
            event += 1
        root += follow*(target-root)
        roots[n], phases[n] = root, phase
        phase += 2*math.pi*root/48000
        if phase >= 2*math.pi:
            phase -= 2*math.pi
    return roots, phases, phase


def branches(models, offsets):
    orders = np.arange(1, models[0]['mean'].shape[0]+1)
    angles = []
    for model, offset in zip(models, offsets):
        z = model['mean'][:, ::2]+1j*model['mean'][:, 1::2]
        base = np.where(abs(z) > 1e-15, np.angle(z), 0.)
        angles.append(np.angle(np.exp(1j*(base+orders[:, None]*offset))))
    angles = np.array(angles)
    deltas = np.empty((max(0, len(models)-1), len(orders), 2))
    for a in range(len(models)-1):
        dl = np.angle(np.exp(1j*(angles[a+1, :, 0]-angles[a, :, 0])))
        rel = angles[a+1, :, 1]-angles[a+1, :, 0]-angles[a, :, 1]+angles[a, :, 0]
        deltas[a, :, 0] = dl
        deltas[a, :, 1] = dl+np.angle(np.exp(1j*rel))
    return angles, deltas


def alignment(models, offsets, count=32):
    rows = []
    for a in range(1, len(models)):
        h = min(count, len(models[a]['mean']))
        order = np.arange(1, h+1)
        p = models[a-1]['mean'][:h, ::2]+1j*models[a-1]['mean'][:h, 1::2]
        q = models[a]['mean'][:h, ::2]+1j*models[a]['mean'][:h, 1::2]
        p *= np.exp(1j*order[:, None]*offsets[a-1])
        cross = (p*q.conj()).sum(axis=1)
        def score(x):
            return float(np.real(np.sum(cross*np.exp(-1j*order*x))))
        def derivative(x):
            return float(np.real(np.sum(-1j*order*cross*np.exp(-1j*order*x))))
        # All unit-circle roots of the finite Fourier derivative, plus a
        # separate dense sign-bracketing path; neither uses the C search grid.
        nonzero = np.flatnonzero(abs(cross) > 0)
        candidates = [0., -math.pi]
        if len(nonzero):
            degree = int(nonzero[-1]+1)
            polynomial = np.zeros(2*degree+1, dtype=complex)
            for i in range(degree):
                polynomial[degree+i+1] += (i+1)*cross[i].conjugate()
                polynomial[degree-i-1] -= (i+1)*cross[i]
            polynomial_roots = np.polynomial.polynomial.polyroots(polynomial)
            candidates += [float(np.angle(x)) for x in polynomial_roots if abs(abs(x)-1) < 1e-6]
            grid = np.linspace(-math.pi, math.pi, 8193)
            d = np.real(np.exp(-1j*grid[:, None]*order[None, :])@(-1j*order*cross))
            for j in np.flatnonzero(d[:-1]*d[1:] < 0):
                candidates.append(optimize.brentq(derivative, grid[j], grid[j+1], xtol=1e-14))
        maximum = max(map(score, candidates))
        actual = score(offsets[a])
        assert maximum-actual < 1e-10
        rows.append(dict(anchor=a, candidates=len(candidates), C_score=actual,
                         independent_maximum=maximum, score_gap=maximum-actual))
    return rows


def selection(roots, base):
    lower = np.searchsorted(base, roots, side='left')-1
    lower = np.clip(lower, 0, len(base)-1)
    upper = np.minimum(lower+1, len(base)-1)
    upper[roots <= base[0]] = 0
    lower[roots >= base[-1]] = len(base)-1
    upper[roots >= base[-1]] = len(base)-1
    blend = np.zeros(len(roots))
    both = lower != upper
    blend[both] = (roots[both]-base[lower[both]])/(base[upper[both]]-base[lower[both]])
    coverage = np.where(roots < base[0]-1e-8, -1, np.where(roots > base[-1]+1e-8, 1, 0))
    return lower, upper, blend, coverage


def sine_table(angle):
    # Analytic values at the grid, interpolated independently of C's stored table.
    u = angle*(4096/(2*math.pi))
    u -= np.floor(u/4096)*4096
    u[u >= 4096] = 0
    cell = np.floor(u)
    fraction = u-cell
    return (1-fraction)*np.sin(2*math.pi*cell/4096)+fraction*np.sin(2*math.pi*(cell+1)/4096)


def sparse(models, base, offsets, seed, roots, phases, indices):
    count, h, k = len(models), *models[0]['basis'].shape[:2]
    assert all(m['basis'].shape[:2] == (h, k) for m in models)
    rng = Gaussian(seed)
    # Equal explicit seeds and equal draw counts give identical innovation
    # sequences in distinct anchor states; this does not align latent bases.
    pc = np.tile([rng.next() for _ in range(k)], (count, 1))
    residual = np.tile(np.array([rng.next() for _ in range(h*4)]).reshape(1, h, 4), (count, 1, 1))
    rho = np.array([m['rho'] for m in models])
    rr = np.array([m['residual_rho'] for m in models])[:, :, None]
    basis = np.array([m['basis'] for m in models])
    factor = np.array([m['root'] for m in models])
    mean = np.array([m['mean'] for m in models])
    def advance():
        nonlocal pc, residual
        z = np.array([rng.next() for _ in range(k)])
        noise = np.array([rng.next() for _ in range(h*4)]).reshape(h, 4)
        pc = rho*pc+np.sqrt(1-rho*rho)*z
        residual = rr*residual+np.sqrt(1-rr*rr)*noise
    def coefficients(p, r):
        return np.einsum('ahkc,ak->ahc', basis, p*np.sqrt(3/(2+rho)))+np.einsum(
            'ahcj,ahj->ahc', factor, r*np.sqrt(3/(2+rr)))
    left_pc, left_residual = pc.copy(), residual.copy()
    advance()
    fraction, updates, selected, values, mid_values = 0., 1, set(indices), [], []
    angle, delta = branches(models, offsets)
    lower, upper, blend, _ = selection(roots, base)
    orders = np.arange(1, h+1)
    for n in range(max(indices)+1):
        while fraction >= 1:
            fraction -= 1
            left_pc, left_residual = pc.copy(), residual.copy()
            advance()
            updates += 1
        if n in selected:
            left, right = coefficients(left_pc, left_residual), coefficients(pc, residual)
            z = mean+left+fraction*(right-left)
            amplitude = np.hypot(z[:, :, ::2], z[:, :, 1::2])
            lo, hi, t = lower[n], upper[n], blend[n]
            if lo == hi or t == 0:
                unit = np.cos(angle[lo])+1j*np.sin(angle[lo])
            elif t == 1:
                unit = np.cos(angle[hi])+1j*np.sin(angle[hi])
            else:
                phase = angle[lo]+t*delta[lo]
                unit = sine_table(phase+math.pi/2)+1j*sine_table(phase)
            magnitude = amplitude[lo]+t*(amplitude[hi]-amplitude[lo])
            x = np.clip((orders*roots[n]-19200)/2400, 0, 1)
            weight = 1-3*x*x+2*x*x*x
            carrier = np.exp(1j*orders*phases[n])
            values.append(np.sum(weight[:, None]*magnitude*np.real(unit*carrier[:, None]), axis=0))
        fraction += roots[n]/12000
    return np.array(values), updates
