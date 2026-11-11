"""Static scientific figure, same gain within each source excerpt."""
from runtime_review import ROOT
import numpy as np
import soundfile as sf
from scipy import signal
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt


def main():
    out = ROOT/'references/analysis/reference_osc_v1'
    fig, axes = plt.subplots(3, 1, figsize=(10, 9), constrained_layout=True)
    for ax, scene, title in zip(axes, ['low', 'blips', 'moving'],
                               ['Exterior low rev', 'Exterior rev sequence', 'Exterior moving']):
        for key, label, color in [('reference', 'Recording', '#555555'),
            ('base', '64 OSC / C', '#187eae'), ('high35', '+ residual high OSC at 35%', '#c67327')]:
            audio, rate = sf.read(out/f'{scene}_{key}_audition.wav', always_2d=True)
            audio = audio[rate//5:-rate//5]
            freq, power = signal.welch(audio, rate, nperseg=8192, axis=0)
            ax.semilogx(freq, 10*np.log10(power.mean(axis=1)+1e-25), color=color, label=label, alpha=.85)
        ax.set(xlim=(80, 16000), ylim=(-130, -20), ylabel='PSD (dBFS/Hz)', title=title)
        ax.axvspan(3000, 14000, color='#c67327', alpha=.05)
        ax.grid(alpha=.2)
    axes[0].legend(fontsize=9)
    axes[-1].set_xlabel('Frequency (Hz) / same gain within each excerpt')
    fig.savefig(out/'spectral_comparison.png', dpi=150)
    plt.close(fig)


if __name__ == '__main__':
    main()
