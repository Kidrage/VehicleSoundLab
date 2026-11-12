"""Observe approved A startup without assigning mechanical event times or RPM."""
import argparse
import json
from pathlib import Path
import shutil
import sys

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--workspace', type=Path, required=True)
p.add_argument('--out', type=Path, required=True)
a = p.parse_args()
repo = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(a.workspace / 'tools/python_deps'))
import numpy as np
from scipy import signal
import soundfile as sf
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from drive_evidence_v1.sources import read, sha

a.out.mkdir(parents=True, exist_ok=False)
for path in (Path(__file__), repo / 'tools/drive_evidence_v1/sources.py'):
    dst = a.out / 'exact_sources' / path.relative_to(repo)
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(path, dst)
r = dict(schema='vsl.startup-layer-observations/1', result='running',
         source_sha256=sha(__file__), physical_event_times_identified=False,
         limits=['One cabin recording, not an exterior startup transfer',
                 'Acoustic onset times do not identify crank, catch, RPM or pedal',
                 'Handling, motor, combustion and cabin sources are not physically separated'])
edges = np.array([30, 120, 300, 600, 1200, 2400, 4800, 8000.])


def powers(x, nperseg=2048):
    f, psd = signal.welch(x, 48000, nperseg=nperseg, axis=0,
                          detrend=False, scaling='density')
    return f, psd, np.array([psd[(f >= lo) & (f < hi)].sum(axis=0) * (f[1]-f[0])
                            for lo, hi in zip(edges[:-1], edges[1:])])


try:
    x, provenance = read(a.workspace, 'A_start_context', 'audio_onset_observation')
    r['input'] = provenance
    # Pure tones independently specify the expected per-channel mean-square.
    t = np.arange(48000) / 48000
    known = np.column_stack([.2*np.sin(2*np.pi*1000*t), .3*np.sin(2*np.pi*200*t)])
    _, _, kp = powers(known, 4800)
    assert np.max(np.abs(kp.sum(axis=0)-np.array([.02, .045]))) < 1e-12
    assert np.argmax(kp[:, 0]) == 3 and np.argmax(kp[:, 1]) == 1
    r['known_power_control_max_error'] = float(np.max(np.abs(kp.sum(axis=0)-[.02, .045])))
    intervals = [('background', 35., 36.2), ('early_broadband', 36.65, 37.12),
                 ('low_frequency_build', 37.22, 38.02), ('settling', 38.25, 39.)]
    r['intervals'] = []
    fig, axes = plt.subplots(2, 1, figsize=(13, 8), constrained_layout=True)
    for label, first, stop in intervals:
        y = x[round((first-33)*48000):round((stop-33)*48000)]
        f, psd, power = powers(y, 4096)
        mono = y.mean(axis=1)
        peaks, _ = signal.find_peaks(psd.mean(axis=1), distance=3)
        peaks = sorted((i for i in peaks if 40 <= f[i] <= 8000),
                       key=lambda i: psd[i].mean(), reverse=True)[:12]
        r['intervals'].append(dict(label=label, seconds=[first, stop],
            band_edges_hz=edges.tolist(), band_power_LR=power.tolist(),
            rms_LR=np.sqrt(np.mean(y*y, axis=0)).tolist(),
            side_mid_dB=float(10*np.log10(max(np.mean(((y[:,0]-y[:,1])*.5)**2),1e-30) /
                                       max(np.mean(mono*mono),1e-30))),
            abs_ge_0_999_fraction_LR=np.mean(np.abs(y)>=.999,axis=0).tolist(),
            abs_gt_1_fraction_LR=np.mean(np.abs(y)>1,axis=0).tolist(),
            spectral_peaks_hz=[float(f[i]) for i in peaks]))
        axes[0].semilogx(f[1:], 10*np.log10(np.maximum(psd[1:].mean(axis=1),1e-30)), label=label)
    axes[0].set(xlim=(30,8000), ylim=(-95,-15), xlabel='Acoustic frequency (Hz)', ylabel='PSD (dBFS/Hz)')
    axes[0].legend()
    f, ts, z = signal.stft(x, 48000, nperseg=2048, noverlap=1808, axis=0,
                          boundary=None, padded=False)
    frame_power = abs(z)**2
    band = np.array([frame_power[(f>=lo)&(f<hi)].sum(axis=0).mean(axis=0)
                     for lo,hi in zip(edges[:-1],edges[1:])])
    ts = ts + 33
    for i in (0,1,3,4,5,6):
        axes[1].plot(ts, 10*np.log10(np.maximum(band[i],1e-30)), label=f'{edges[i]:g}-{edges[i+1]:g} Hz')
    axes[1].set(xlim=(36.3,39.2), xlabel='Decoded audio source seconds', ylabel='Window band energy (dBFS)')
    axes[1].legend(ncol=3)
    fig.savefig(a.out / 'startup_layers.png', dpi=140)
    plt.close(fig)
    # Keep original samples for review, common fixed gain only.
    for label, first, stop in intervals[1:]:
        y = x[round((first-33)*48000):round((stop-33)*48000)].copy()*.5
        fade = min(240,len(y)//2)
        y[:fade] *= np.linspace(0,1,fade)[:,None]
        y[-fade:] *= np.linspace(1,0,fade)[:,None]
        sf.write(a.out / (label+'.wav'), y, 48000, subtype='FLOAT')
    r.update(result='observed_only', candidate_source='early_broadband',
             review_gain=.5, review_fade_samples=240,
             next='Fit a separate pre-low-rise statistical mechanical texture, not the continuous DNA or a physical crank label')
except Exception as exc:
    r.update(result='failed', error=repr(exc))
    raise
finally:
    (a.out/'report.json').write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({k:r[k] for k in ('result','known_power_control_max_error','intervals')},ensure_ascii=True))
