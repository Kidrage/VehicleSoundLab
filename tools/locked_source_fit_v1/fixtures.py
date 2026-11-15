"""Same original known geometry/scales; distinct new audio and old calibration."""
import numpy as np
from waveform_file_real_v1.fixtures import cases as original_cases
from observer_frequency_v1.reduced_oracle import synthesize


def cases():
    for z in original_cases():
        z['metric_target'] = z['target'].copy()
        h = np.arange(len(z['orders']))[None, :, None]
        changed = z['source_nodes']*(.72+.09*h)*np.exp(.11j*h)
        audio = synthesize(changed*z['scale'][None], z['positions'], z['orders'], len(z['audio']))
        if z['label'] != 'both_zero':
            n = np.arange(len(audio)); endpoint = 1e-6*(1+(-1.)**n)
            audio[:, 0] += endpoint
            if z['label'] != 'silent_right': audio[:, 1] += .37*endpoint
        z.update(audio=audio, target=audio[2048:-2048].copy(), new_source_nodes=changed)
        yield z
