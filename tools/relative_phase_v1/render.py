"""Paired offline OSC sounds; identical amplitudes, independent spatial rendering."""
import numpy as np
import soundfile as sf
from radial_copula_v1.latent import endpoints, features
from .coordinates import decode


def render_pair(folder, model, root, seconds, seed, block=1024, suffix=''):
    frames = round(seconds*48000)
    state, _ = endpoints(model, int(np.floor((frames-1)*root/12000))+2, seed)
    orders = np.arange(1, len(model['fixed_phase'])+1)
    x = np.clip((orders*root-19200)/2400, 0, 1)
    taper = 1-3*x*x+2*x*x*x
    peaks = dict(fixed_phase=0., relative_phase=0.)
    paths = {key: folder/f'{key}_{seed}{suffix}.wav' for key in peaks}
    with sf.SoundFile(paths['fixed_phase'], mode='x', samplerate=48000, channels=2, subtype='FLOAT') as fixed, \
         sf.SoundFile(paths['relative_phase'], mode='x', samplerate=48000, channels=2, subtype='FLOAT') as relative:
        streams = dict(fixed_phase=fixed, relative_phase=relative)
        for start in range(0, frames, block):
            n = np.arange(start, min(frames, start+block)); position = n*root/12000
            at = np.floor(position).astype(int)
            normal = features(model, state, at, position-at)
            amplitude, phase = decode(model, normal)
            base = np.remainder(2*np.pi*n*root/48000, 2*np.pi)
            for key, angle in [('fixed_phase', model['fixed_phase']), ('relative_phase', phase)]:
                audio = np.sum(amplitude*taper[None, :, None]*np.cos(base[:, None, None]*orders[None, :, None]+angle), axis=1)
                assert np.isfinite(audio).all()
                peaks[key] = max(peaks[key], float(abs(audio).max()))
                streams[key].write(audio.astype('float32'))
    return [dict(variant=key, file=path.name, seed=seed, frames=frames, root_hz=root,
                 block=block, peak_FS=peaks[key], texture_endpoints=len(state)) for key, path in paths.items()]
