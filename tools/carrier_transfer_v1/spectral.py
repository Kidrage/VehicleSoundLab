"""Full group/channel Gram matrices preserve signed spectral interference."""
import numpy as np


def measure(audio, root, bands, harmonics=288):
    frames, groups, channels = audio.shape
    assert channels == 2
    size = 4096
    window = .5-.5*np.cos(2*np.pi*np.arange(size)/size)
    starts = np.arange(0, frames-size+1, 256)
    flat = audio.reshape(frames, 2*groups)
    windows = np.array([flat[start:start+size]*window[:, None] for start in starts])
    transform = np.fft.rfft(windows, axis=1)
    frequency = np.fft.rfftfreq(size, 1/(1024*root))
    scale = np.full(len(frequency), 2/(size*np.dot(window, window)))
    scale[[0, -1]] /= 2
    def gram(value, weights):
        return (value.transpose(0, 2, 1)*weights)@value.conj()
    line, broad = [], []
    orders = np.arange(1, harmonics+1)
    for lo, hi in bands:
        mask = (frequency >= lo)&(frequency < hi)
        broad.append(gram(transform[:, mask], scale[mask]))
        index = 4*orders[(orders*root >= lo)&(orders*root < hi)]
        line.append(gram(transform[:, index], np.full(len(index), 2/window.sum()**2)))
    all_frequency = gram(transform, scale)
    time_energy = windows.transpose(0, 2, 1)@windows/np.dot(window, window)
    return dict(starts=starts, line_Gram=np.stack(line, axis=1), broad_Gram=np.stack(broad, axis=1),
                all_frequency_Gram=all_frequency, time_energy_Gram=time_energy)


def collapse(matrix):
    groups = matrix.shape[-1]//2
    shaped = matrix.reshape(*matrix.shape[:-2], groups, 2, groups, 2)
    return shaped.sum(axis=(-4, -2))


def summary(matrix):
    mean = matrix.mean(axis=0)
    groups = mean.shape[-1]//2
    diagonal = np.diagonal(mean, axis1=-2, axis2=-1).real.reshape(-1, groups, 2)
    shaped = mean.reshape(-1, groups, 2, groups, 2)
    stereo = collapse(mean)
    low = diagonal[:, 0]
    rest = shaped[:, 1:, :, 1:, :].sum(axis=(1, 3))[:, [0, 1], [0, 1]].real
    low_rest = 2*shaped[:, 0, :, 1:, :].sum(axis=2)[:, [0, 1], [0, 1]].real
    return dict(group_self_power=diagonal, low_power=low, rest_power=rest,
                signed_low_rest_cross=low_rest,
                signed_all_group_cross=stereo[:, [0, 1], [0, 1]].real-diagonal.sum(axis=1),
                total_power=stereo[:, [0, 1], [0, 1]].real,
                complex_LR=stereo[:, 0, 1])
