"""Plot only the confirmed exterior overlap, at the unchanged audition gain."""
from runtime_review import ROOT
import json
import numpy as np
import soundfile as sf
from scipy import signal
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt


def main():
    out = ROOT/'references/analysis/reference_osc_v2'
    report = json.loads((out/'results.json').read_text(encoding='utf-8'))
    fig, ax = plt.subplots(figsize=(10, 4.8), constrained_layout=True)
    for name, label, color in [('base', 'Accepted64 / C', '#227eb1'), ('high25', '+ measured high at25%', '#48a17b'), ('high50', '+ measured high at50%', '#c87929')]:
        audio, rate = sf.read(out/report['auditions'][name]['file'])
        audio = audio[round(2.7*rate):round(5.8*rate)]
        freq, power = signal.welch(audio, rate, nperseg=8192)
        ax.semilogx(freq, 10*np.log10(power+1e-25), label=label, color=color, alpha=.85)
    ax.set(xlim=(80, 16000), ylim=(-135, -25), xlabel='Frequency (Hz)', ylabel='PSD (dBFS/Hz)',
           title='Accepted64 base + separate high OSC / same gain / exterior overlap')
    ax.grid(alpha=.2)
    ax.legend(fontsize=9)
    fig.savefig(out/'spectral_comparison.png', dpi=150)
    plt.close(fig)


if __name__ == '__main__':
    main()
