"""Frozen-state paired replay, applying only the known relative-phase lift."""
import numpy as np
from scipy.special import ndtr
from radial_copula_v1.latent import features
from radial_copula_v1.quantiles import lookup
from conditional_phase_time_v1.mapping import decode
from carrier_transfer_v1.groups import indices
from .lift import lift_block


def generate(bundle, capture, root, edges, block=1024):
    model = {name[6:]:value for name, value in bundle.items() if name.startswith('model_')}
    h = len(model['fixed_phase'])
    orders = np.arange(1, h+1)
    frames = len(capture['fixed_audio'])
    tags = indices(h, root, edges)
    variants = ('fixed', 'relative', 'parent', 'density', 'variation')
    grouped = {name:np.empty((frames, len(edges)-1, 2)) for name in variants}
    diagnostics = {}
    states = {name:None for name in variants[1:]}
    taper_x = np.clip((orders*root-19200)/2400, 0, 1)
    taper = 1-3*taper_x*taper_x+2*taper_x*taper_x*taper_x
    for name in variants[1:]:
        diagnostics[name] = dict(branch_counts=np.zeros(h, np.int64), changed_samples=np.zeros(h, np.int64),
            ambiguous_steps=np.zeros(h, np.int64), maximum_raw_step=np.zeros(h), maximum_lifted_step=np.zeros(h),
            minimum_half_turn_margin=np.full(h, np.inf), maximum_circular_error=0., maximum_gauge_wave_error=0.)
    original_errors = dict.fromkeys(variants, 0.)
    partition_errors = dict.fromkeys(variants, 0.)
    probes = capture['probe_positions']
    saved_probes = {name:np.empty((len(probes), h)) for name in variants[1:]}
    for first in range(0, frames, block):
        n = np.arange(first, min(first+block, frames))
        u = (n%256)/256
        normal = features(model, capture['state'], n//256, u)
        extra = features(model, capture['independent_state'], n//256, u)
        amplitude = lookup(model['amplitude'], normal[:, :2*h]).reshape(-1, h, 2)
        common = lookup(model['phase'][:, :h], normal[:, 2*h:3*h])
        deltas = dict(relative=lookup(model['phase'][:, h:], normal[:, 3*h:]))
        product = amplitude[..., 0]*amplitude[..., 1]/bundle['mean_product']
        uniform = ndtr(extra[:, 3*h:])
        for name in ('parent', 'density', 'variation'):
            deltas[name] = np.column_stack([decode(product[:, j], uniform[:, j], bundle['knots'][j],
                bundle[name][j], bundle['low'][j], bundle['high'][j]) for j in range(h)])
        amplitude = amplitude*taper[None, :, None]
        base = 2*np.pi*(n%1024)/1024
        carrier = base[:, None, None]*orders[None, :, None]
        mask = (probes >= first)&(probes < first+len(n))
        at = probes[mask]-first
        for name in variants:
            angle = model['fixed_phase'] if name == 'fixed' else np.stack([common+deltas[name]/2, common-deltas[name]/2], axis=-1)
            original = np.sum(amplitude*np.cos(carrier+angle), axis=1)
            original_errors[name] = max(original_errors[name], float(abs(original-capture[name+'_audio'][n]).max()))
            if name != 'fixed':
                delta = deltas[name]
                previous = states[name]
                lifted, states[name], info = lift_block(delta, previous)
                track_raw = np.vstack([previous.previous_raw, delta]) if previous is not None else delta
                previous_lift = previous.previous_raw-2*np.pi*previous.winding if previous is not None else None
                track_lift = np.vstack([previous_lift, lifted]) if previous is not None else lifted
                raw_steps, lifted_steps = np.diff(track_raw, axis=0), np.diff(track_lift, axis=0)
                d = diagnostics[name]
                d['branch_counts'] += np.count_nonzero(info['increments'], axis=0)
                d['changed_samples'] += np.count_nonzero(info['winding'], axis=0)
                d['ambiguous_steps'] += np.count_nonzero(info['half_turn_ambiguous'], axis=0)
                d['maximum_raw_step'] = np.maximum(d['maximum_raw_step'], abs(raw_steps).max(axis=0))
                d['maximum_lifted_step'] = np.maximum(d['maximum_lifted_step'], abs(lifted_steps).max(axis=0))
                margin = abs(abs(raw_steps/(2*np.pi)-np.rint(raw_steps/(2*np.pi)))-.5)*2*np.pi
                d['minimum_half_turn_margin'] = np.minimum(d['minimum_half_turn_margin'], margin.min(axis=0))
                d['maximum_circular_error'] = max(d['maximum_circular_error'], float(abs(np.exp(1j*lifted)-np.exp(1j*delta)).max()))
                angle = np.stack([common+lifted/2, common-lifted/2], axis=-1)
                if mask.any():
                    saved_probes[name][mask] = info['winding'][at]
                    compensated_common = common[at]+np.pi*info['winding'][at]
                    compensated = np.stack([compensated_common+lifted[at]/2, compensated_common-lifted[at]/2], axis=-1)
                    gauge = np.sum(amplitude[at]*np.cos(carrier[at]+compensated), axis=1)
                    d['maximum_gauge_wave_error'] = max(d['maximum_gauge_wave_error'], float(abs(gauge-original[at]).max()))
            partials = amplitude*np.cos(carrier+angle)
            for group in range(len(edges)-1):
                grouped[name][first:first+len(n), group] = partials[:, tags == group].sum(axis=1)
            partition_errors[name] = max(partition_errors[name], float(abs(partials.sum(axis=1)-grouped[name][first:first+len(n)].sum(axis=1)).max()))
    for name in variants[1:]:
        diagnostics[name]['terminal_winding'] = states[name].winding
        diagnostics[name]['probe_winding'] = saved_probes[name].astype(np.int64)
    return grouped, diagnostics, original_errors, partition_errors
