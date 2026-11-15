"""Paired continuous OSC probes on the original acoustic sample coordinate."""
import numpy as np
from scipy.special import ndtr
from radial_copula_v1.latent import endpoints, features
from radial_copula_v1.quantiles import lookup
from .mapping import decode
from .observer import coefficient_powers, power_statistics


def generate(model, maps, root, bands, cycles, seed, block=1024):
    frames = 1024*cycles
    harmonics = len(model['fixed_phase'])
    state, _ = endpoints(model, (frames-1)//256+2, seed)
    independent_state, _ = endpoints(model, len(state), np.random.SeedSequence([seed, 789783]))
    variants = ('fixed', 'relative', 'parent', 'density', 'variation')
    audio = {key:np.empty((frames, 2)) for key in variants}
    power = {key:np.empty((frames, 2*len(bands))) for key in variants}
    cross = {key:np.empty((frames, len(bands)), complex) for key in variants}
    orders = np.arange(1, harmonics+1)
    x = np.clip((orders*root-19200)/2400, 0, 1)
    taper = 1-3*x*x+2*x*x*x
    probes = np.unique(np.rint(np.linspace(0, frames-1, 37)).astype(int))
    capture = dict(state=state, independent_state=independent_state, probe_positions=probes)
    outside = np.zeros((harmonics, 2), np.int64)
    maximum_step = {key:np.zeros(harmonics) for key in ('relative', 'parent', 'density', 'variation')}
    previous = {}
    for start in range(0, frames, block):
        n = np.arange(start, min(frames, start+block))
        position = n/256
        at = n//256
        fraction = position-at
        normal = features(model, state, at, fraction)
        extra = features(model, independent_state, at, fraction)
        amplitude = lookup(model['amplitude'], normal[:, :2*harmonics]).reshape(-1, harmonics, 2)
        common = lookup(model['phase'][:, :harmonics], normal[:, 2*harmonics:3*harmonics])
        relative = lookup(model['phase'][:, harmonics:], normal[:, 3*harmonics:])
        uniform = ndtr(extra[:, 3*harmonics:])
        product = amplitude[..., 0]*amplitude[..., 1]/maps['mean_product']
        outside[:, 0] += np.sum(product < maps['knots'][:, 0], axis=0)
        outside[:, 1] += np.sum(product > maps['knots'][:, -1], axis=0)
        deltas = dict(relative=relative)
        for key in ('parent', 'density', 'variation'):
            deltas[key] = np.column_stack([decode(product[:, h], uniform[:, h], maps['knots'][h],
                maps[key][h], maps['low'][h], maps['high'][h]) for h in range(harmonics)])
        angles = dict(fixed=model['fixed_phase'])
        for key, delta in deltas.items():
            angles[key] = np.stack([common+delta/2, common-delta/2], axis=-1)
            track = np.vstack([previous[key], delta]) if key in previous else delta
            if len(track) > 1:
                maximum_step[key] = np.maximum(maximum_step[key], abs(np.diff(track, axis=0)).max(axis=0))
            previous[key] = delta[-1]
        probe_mask = (probes >= start)&(probes < start+len(n))
        if probe_mask.any():
            local = probes[probe_mask]-start
            for name, value in [('normal', normal), ('independent_normal', extra), ('amplitude', amplitude),
                                ('common', common), ('relative', relative), ('uniform', uniform)]:
                if 'probe_'+name not in capture:
                    capture['probe_'+name] = np.empty((len(probes),)+value.shape[1:])
                capture['probe_'+name][probe_mask] = value[local]
        base = 2*np.pi*(n % 1024)/1024
        amplitude = amplitude*taper[None, :, None]
        for key in variants:
            angle = angles[key]
            z = amplitude*np.exp(1j*angle)
            power[key][start:start+len(n)], cross[key][start:start+len(n)] = coefficient_powers(z, root, bands)
            audio[key][start:start+len(n)] = np.sum(amplitude*np.cos(
                base[:, None, None]*orders[None, :, None]+angle), axis=1)
    capture['outside_P_counts'] = outside
    for key in maximum_step:
        capture[key+'_maximum_unwrapped_relative_phase_step'] = maximum_step[key]
    for key in variants:
        capture[key+'_audio'] = audio[key]
        capture.update({key+'_instant_'+name:value for name, value in power_statistics(power[key], cross[key]).items()})
    return capture
