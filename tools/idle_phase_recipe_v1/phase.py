"""Optional statistical acoustic phase motion; no PCM or mechanical clock claim."""
import numpy as np
from scipy import interpolate, linalg, signal

M = np.array([[-1., -1., 1.], [3., -2., 0.]])
H = np.array([2., 3., 5.])
RIGHT = M.T @ np.linalg.inv(M @ M.T)
INDICES = [1, 2, 4]


def coordinates(z):
    return np.column_stack((z[:, 2]*z[:, 1].conj()*z[:, 0].conj(),
                            z[:, 0]**3*z[:, 1].conj()**2))


def fit(phasors, rate=48000, node_rate=200):
    w = coordinates(phasors)
    center = np.angle(w.mean(axis=0))
    native = np.angle(w*np.exp(-1j*center))
    if np.any(abs(native).max(axis=0) >= np.pi-.05):
        raise ValueError('Source coordinate chart unresolved')
    x = signal.resample_poly(native, 1, rate//node_rate, window=('kaiser', 8.6), padtype='line')
    offset = x.mean(axis=0); x -= offset
    design = np.column_stack((x[1:-1], x[:-2])); target = x[2:]
    beta, _, rank, singular = np.linalg.lstsq(design, target, rcond=None)
    if rank != 4:
        raise ValueError('Unresolved VAR2 design')
    transition = np.zeros((4, 4)); transition[:2] = beta.T; transition[2:, :2] = np.eye(2)
    radius = float(abs(np.linalg.eigvals(transition)).max())
    if radius >= 1:
        raise ValueError(f'Unstable source VAR2: {radius}; do not clip poles')
    error = target-design@beta; covariance = error.T@error/len(error)
    injection = np.zeros((4, 4)); injection[:2, :2] = covariance
    stationary = linalg.solve_discrete_lyapunov(transition, injection)
    if np.linalg.eigvalsh(covariance).min() <= 0 or np.linalg.eigvalsh(stationary).min() <= 0:
        raise ValueError('Nonpositive covariance; do not clip eigenvalues')
    theta = np.unwrap(np.angle(phasors), axis=0)
    phi = theta@H/(H@H)
    t = np.arange(len(phi))/rate
    carrier = np.linalg.lstsq(np.column_stack((np.ones(len(t)), t)), phi, rcond=None)[0]
    return dict(schema='vsl.idle-phase-statistics/1', node_rate=node_rate,
        coordinate_center=(center+offset).tolist(), transition=transition.tolist(),
        innovation_covariance=covariance.tolist(), stationary_covariance=stationary.tolist(),
        carrier_phase_rad=float(carrier[0]), carrier_hz=float(carrier[1]/(2*np.pi)),
        training_covariance=(x.T@x/len(x)).tolist(), spectral_radius=radius,
        design_rank=int(rank), design_condition=float(singular[0]/singular[-1]),
        source_frames=len(phasors), PCM_or_phase_trajectory=False,
        scope='Stationary Gaussian VAR2 acoustic hypothesis; not real crank dynamics')


def nodes(model, seed, seconds):
    """Fixed stationary initial draw, then recurrence; independent RNG streams."""
    count = int(np.ceil(seconds*model['node_rate']))+5
    initial = np.random.Generator(np.random.PCG64(seed ^ 0x1DB87B43124A)).standard_normal(4)
    normal = np.random.Generator(np.random.PCG64(seed ^ 0xA4F91CD27855)).standard_normal((count-1, 2))
    state = np.linalg.cholesky(model['stationary_covariance'])@initial
    root = np.linalg.cholesky(model['innovation_covariance'])
    transition = np.asarray(model['transition']); out = np.empty((count, 2)); out[0] = state[:2]
    for j in range(1, count):
        state = transition@state; state[:2] += root@normal[j-1]; out[j] = state[:2]
    return out+np.asarray(model['coordinate_center'])


def spline(model, values):
    # Two extra past nodes keep t=0 away from the natural boundary.
    return interpolate.CubicSpline((np.arange(len(values))-2)/model['node_rate'], values, bc_type='natural')


def phasors(model, motion, t):
    u = motion(t)
    phi = model['carrier_phase_rad']+2*np.pi*model['carrier_hz']*t
    return np.exp(1j*(phi[:, None]*H+u@RIGHT.T))


def known():
    assert abs(M@RIGHT-np.eye(2)).max() < 1e-14
    assert abs(M@H).max() == 0
    theta = np.arange(600)[:, None]*[.13, .19, .37]+[.2, -.4, .7]
    z = np.exp(1j*theta); w = coordinates(z)
    err = float(abs(w-np.exp(1j*theta@M.T)).max()); assert err < 1e-12
    a = np.array([[.81,.02,0,0],[-.01,.76,0,0],[1,0,0,0],[0,1,0,0]])
    q = np.diag([.03,.05,0,0]); p = linalg.solve_discrete_lyapunov(a,q)
    lyap = float(abs(p-a@p@a.T-q).max()); assert lyap < 1e-14
    constant = dict(node_rate=200); y = np.tile([.2,-.7], (100,1)); s = spline(constant,y)
    interp = float(abs(s(np.arange(4000)/48000)-[.2,-.7]).max()); assert interp < 1e-14
    return dict(coordinate_algebra=err, lyapunov_residual=lyap, constant_interpolation_error=interp,
                stationary_covariance_positive=bool(np.linalg.eigvalsh(p).min()>0))
