"""Energy represented by sparse harmonic readings versus full Hann cells."""
import numpy as np


def measure(audio, harmonics=288):
    size, hop, cycle = 4096, 256, 1024
    if len(audio) < size+hop or not 1 <= harmonics <= 320:
        raise ValueError('Complete four-cycle observations and1..320harmonics required')
    window = np.hanning(size+1)[:-1]
    indices = np.arange(1, harmonics+1)*4
    cells = indices[:, None] + np.arange(-2, 2)
    projected, complete = [], []
    for start in range(0, len(audio)-size+1, hop):
        z = np.fft.rfft(audio[start:start+size]*window[:, None], axis=0)
        projected.append(2*abs(z[indices])**2/window.sum()**2)
        complete.append(2*np.sum(abs(z[cells])**2, axis=1)/(size*np.sum(window**2)))
    projected, complete = np.mean(projected, axis=0), np.mean(complete, axis=0)
    hz = np.arange(1, harmonics+1)*48000/cycle
    bands = []
    for low, high in [(28,120),(120,400),(400,1200),(1200,3000),(3000,8000),(8000,14000)]:
        selected = (hz >= low) & (hz < high)
        a, b = projected[selected].sum(axis=0), complete[selected].sum(axis=0)
        bands.append(dict(hz=[low,high], harmonic_count=int(selected.sum()),
            full_cell_power_LR=b.tolist(), projected_power_LR=a.tolist(),
            projected_minus_cell_db_LR=(10*np.log10((a+1e-30)/(b+1e-30))).tolist()))
    return dict(windows=len(range(0,len(audio)-size+1,hop)),
        bands=bands, projected_fraction_LR=(projected.sum(axis=0)/complete.sum(axis=0)).tolist(),
        theoretical_white_noise_fraction=float(np.sum(window**2)/window.sum()**2*cycle),
        definition='Cell has4FFT bins centered on each acoustic harmonic; coherent Hann lobe fits cell. Sparse reading uses only its central bin.',
        limits='Budget of this analysis window; not source separation, a noise gain recipe, or a perceptual quality metric')
