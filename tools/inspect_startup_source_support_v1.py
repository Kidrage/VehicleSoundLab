"""Diagnose temporal/frequency support without fitting or moving source crops."""
import argparse
from copy import deepcopy
from pathlib import Path
import shutil

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
from scipy import signal

from event_authoring.audio import read
from event_authoring.model import synth
from event_authoring.native import Renderer, controls
from research_archive_v1 import load, save, sha

EDGES = ((60, 300), (300, 1200), (1200, 4500), (4500, 14000))


def curves(wave):
    wave = np.asarray(wave, dtype=float)
    if wave.ndim == 1:
        wave = wave[:, None]
    f, t, p = signal.spectrogram(wave, 48000, window='hann', nperseg=1024,
        noverlap=928, detrend=False, scaling='density', mode='psd', axis=0)
    p = p.mean(axis=1)
    energy = np.array([p[(f >= lo)&(f < hi)].sum(axis=0)*(f[1]-f[0]) for lo, hi in EDGES])
    return f, t, p, energy


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    out = parser.parse_args().output
    out.mkdir(parents=True, exist_ok=False)
    repo = Path(__file__).resolve().parents[1]
    original = load(Path('E:/VehicleSoundLab/references/analysis/A_exterior_startup_v1/verification5/report.json'))
    renderer = Renderer(repo)
    for p in [Path(__file__), *sorted((repo/'tools/event_authoring').glob('*.py'))]:
        dest = out/'exact_sources'/p.relative_to(repo)
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(p, dest)
    fig, axes = plt.subplots(4, 2, figsize=(12, 10), layout='constrained')
    cases = []
    for column, kind in enumerate(('crank', 'catch')):
        document = Path(original['profiles'][kind]['document'])
        doc = load(document)
        p = doc['parameters']
        job = doc['source_job']
        x, rate, source = read(job['source'], *job['seconds'])
        bg, _, background = read(job['source'], *job['background_seconds'])
        f, t, power, reference = curves(x)
        reference = np.maximum(reference-curves(bg)[3].mean(axis=1)[:, None], 0)
        components, samples = [], []
        for group, index in [('modes', -1), *[('bands', i) for i in range(len(p['bands']))]]:
            isolated = deepcopy(p)
            for category in ('modes', 'bands'):
                for i, item in enumerate(isolated[category]):
                    if category != group or (index >= 0 and i != index):
                        item['amplitude'] = 0.
            wave, _ = renderer.render(isolated, kind, controls(dict(seconds=len(x)/rate+.15,
                hold_seconds=len(x)/rate, seed=27431)))
            samples.append(wave)
            _, _, _, energy = curves(wave[:len(x)])
            early = t < .12
            center = None if group == 'modes' else p['bands'][index]['hz']
            components.append(dict(group=group, index=index, nominal_hz=center,
                early_power=energy[:, early].mean(axis=1).tolist(),
                total_power=energy.mean(axis=1).tolist()))
            for band, ax in enumerate(axes[:, column]):
                ax.plot(t, energy[band], lw=.7, alpha=.8, label=group+str(index))
        full, _ = renderer.render(p, kind, controls(dict(seconds=len(x)/rate+.15,
            hold_seconds=len(x)/rate, seed=27431)))
        linear_error = float(np.max(abs(np.sum(samples, axis=0)-full)))
        assert linear_error < 3e-7
        _, _, _, full_curves = curves(full[:len(x)])
        normalized = reference/np.maximum(reference.mean(axis=1), 1e-30)[:, None]
        model_normalized = full_curves/np.maximum(full_curves.mean(axis=1), 1e-30)[:, None]
        for band, ax in enumerate(axes[:, column]):
            ax.plot(t, reference[band], color='black', lw=1.1, label='material excess')
            ax.plot(t, full_curves[band], color='#cc3c25', lw=.8, label='full C')
            ax.set_title(kind+' / '+str(EDGES[band])+' Hz')
            ax.set_yscale('log')
            ax.set_ylim(max(float(reference[band].max())*1e-5, 1e-15),
                        max(float(reference[band].max()), float(full_curves[band].max()))*2)
            if band == 0:
                ax.legend(fontsize=6)
        np.savez(out/(kind+'-observations.npz'), seconds=t, target=reference,
                 full=full_curves, target_normalized=normalized, full_normalized=model_normalized)
        cases.append(dict(kind=kind, document=str(document), document_sha256=sha(document),
            source=source, background=background, C_component_sum_error_FS=linear_error,
            early_seconds=[0., .12], components=components,
            early_target_power=reference[:, t < .12].mean(axis=1).tolist(),
            early_generated_power=full_curves[:, t < .12].mean(axis=1).tolist(),
            contours=[dict(low_hz=c['low_hz'], high_hz=c['high_hz'],
                members_modes=[i for i, m in enumerate(p['modes']) if c['low_hz'] <= m['hz'] < c['high_hz']],
                members_noise=[i for i, b in enumerate(p['bands']) if c['low_hz'] <= b['hz'] < c['high_hz']],
                seconds=c['seconds'], gains=c['gain']) for c in p['contours']]))
    fig.savefig(out/'component-support.png', dpi=160)
    plt.close(fig)
    x, _, context = read(cases[0]['source']['path'], 48.0, 48.4)
    f, t, p, energy = curves(x)
    fig, axes = plt.subplots(2, 1, figsize=(11, 7), layout='constrained')
    axes[0].pcolormesh(t+48., f, 10*np.log10(np.maximum(p, 1e-20)),
        shading='nearest', vmin=-100, vmax=-30, cmap='magma')
    axes[0].set_ylim(1000, 16000)
    axes[0].axvline(48.18, color='cyan', lw=1)
    for i in (2, 3):
        axes[1].plot(t+48., energy[i], label=str(EDGES[i])+' Hz')
    axes[1].axvline(48.18, color='black', ls='--', label='current stage boundary')
    axes[1].legend()
    axes[1].set_xlabel('original material seconds')
    fig.savefig(out/'transition-context.png', dpi=160)
    plt.close(fig)
    save(out/'report.json', dict(result='passed', fit_performed=False, cases=cases,
        transition_context=context, renderer_sha256=renderer.identity,
        limitations='Short Hann observations are acoustic support, not source separation, physical ignition timing or measured RPM. Component powers do not sum in the presence of cross terms.',
        goal_complete=False, timbre_accepted=False))
    print('actual C component support and original transition context captured; no fit', flush=True)


if __name__ == '__main__':
    main()
