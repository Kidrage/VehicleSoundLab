"""Replay exact frozen states and coefficients, partitioning their carrier sum."""
import numpy as np
from scipy.special import ndtr
from radial_copula_v1.latent import features
from radial_copula_v1.quantiles import lookup
from conditional_phase_time_v1.mapping import decode
from .groups import indices


def generate(bundle, state, independent_state, root, frames, edges, block=1024):
    model = {key[6:]:value for key, value in bundle.items() if key.startswith('model_')}
    h = len(model['fixed_phase'])
    orders = np.arange(1, h+1)
    group = indices(h, root, edges)
    variants = ('fixed', 'relative', 'parent', 'density', 'variation')
    output = {name:np.empty((frames, len(edges)-1, 2)) for name in variants}
    x = np.clip((orders*root-19200)/2400, 0, 1)
    taper = 1-3*x*x+2*x*x*x
    for first in range(0, frames, block):
        n = np.arange(first, min(first+block, frames))
        u = (n%256)/256
        normal = features(model, state, n//256, u)
        extra = features(model, independent_state, n//256, u)
        amplitude = lookup(model['amplitude'], normal[:, :2*h]).reshape(-1, h, 2)
        common = lookup(model['phase'][:, :h], normal[:, 2*h:3*h])
        deltas = dict(relative=lookup(model['phase'][:, h:], normal[:, 3*h:]))
        product = amplitude[..., 0]*amplitude[..., 1]/bundle['mean_product']
        uniform = ndtr(extra[:, 3*h:])
        for name in ('parent', 'density', 'variation'):
            deltas[name] = np.column_stack([decode(product[:, j], uniform[:, j], bundle['knots'][j],
                bundle[name][j], bundle['low'][j], bundle['high'][j]) for j in range(h)])
        base = 2*np.pi*(n%1024)/1024
        amplitude *= taper[None, :, None]
        for name in variants:
            angle = model['fixed_phase'] if name == 'fixed' else np.stack([common+deltas[name]/2, common-deltas[name]/2], axis=-1)
            partials = amplitude*np.cos(base[:, None, None]*orders[None, :, None]+angle)
            for tag in range(len(edges)-1):
                output[name][first:first+len(n), tag] = partials[:, group == tag].sum(axis=1)
    return output, group
