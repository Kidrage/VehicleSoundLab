"""Standalone scientific figures for the processing-quality diagnosis."""
from runtime_review import ROOT
import json
import numpy as np
import soundfile as sf
from scipy import signal
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt


def main():
    out = ROOT/'references/analysis/osc_quality_v1'
    original = json.loads((out/'results.json').read_text(encoding='utf-8'))
    refined = json.loads((out/'refinement/results.json').read_text(encoding='utf-8'))
    values = [original['controls']['am25']['4096']['retained_known_AM_db'],
        original['controls']['am25']['1024']['retained_known_AM_db'],
        refined['controls']['am25']['retained_known_AM_db']]
    fig, ax = plt.subplots(figsize=(8.4, 4.6), constrained_layout=True)
    bars = ax.bar(['Old85ms analysis', 'Short21ms only', 'Long frequency + short joint fit'], values,
                  color=['#aa655a', '#b9a575', '#398c85'], width=.6)
    ax.axhline(0, color='#555555', linewidth=1)
    for bar, value in zip(bars, values):
        ax.text(bar.get_x()+bar.get_width()/2, value-.7, f'{value:.1f} dB', ha='center', va='top')
    ax.set(ylim=(-40, 2), ylabel='Retained25Hz amplitude modulation (dB relative to input)',
        title='Known two-tone AM control: fast envelope detail is lost in long analysis')
    ax.grid(axis='y', alpha=.2)
    fig.savefig(out/'am_control.png', dpi=150)
    plt.close(fig)
    fig, axes = plt.subplots(3, 1, figsize=(10, 8.4), constrained_layout=True, sharex=True, sharey=True)
    for ax, path, title in zip(axes, [out/'reference_audition.wav', out/'legacy64_audition.wav', out/'refinement/joint64_c_audition.wav'],
        ['Recording input / historical mono', 'Original64OSC', 'Same64 frequencies / short joint AM-phase fit / C']):
        audio, rate = sf.read(path)
        f, t, z = signal.stft(audio, rate, nperseg=1024, noverlap=896, boundary=None)
        view = (f >= 80)&(f <= 6000)
        image = ax.pcolormesh(t, f[view]/1000, 20*np.log10(abs(z[view])+1e-12), shading='auto', cmap='magma', vmin=-100, vmax=-30)
        ax.set(title=title, ylabel='kHz', xlim=(2.6, 5.8))
    axes[-1].set_xlabel('Seconds in archival six-second excerpt / exterior overlap shown')
    fig.colorbar(image, ax=axes, label='STFT magnitude (dBFS) / same gain', shrink=.8)
    fig.savefig(out/'spectrogram.png', dpi=150)
    plt.close(fig)


if __name__ == '__main__':
    main()
