"""Measure startup controls and event overlap without altering generated audio."""
import argparse
import json
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import soundfile as sf

from event_authoring.audio import read, sha
from event_designer.package import write_json
from startup_handoff_v1.measure import observe, stereo_groups, marker_bands


def envelope(x, hop=240):
    length = len(x)//hop*hop
    return np.sqrt(np.mean(x[:length].reshape(-1, hop, 2)**2, axis=(1, 2)))


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--captures', type=Path, nargs='+', required=True)
    p.add_argument('--output', type=Path, required=True)
    args=p.parse_args();args.output.mkdir(parents=True, exist_ok=False)
    observations=[observe(path) for path in args.captures]
    raw, rate, provenance=read(Path('E:/VehicleSoundLab/references/clean/A_decoded_float.wav'), 35., 40.5)
    sf.write(args.output/'A35-40.5-original.wav', raw, rate, subtype='FLOAT')
    sf.write(args.output/'A35-40.5-monitor.wav', .25*raw, rate, subtype='FLOAT')
    figure, axes=plt.subplots(3, 1, figsize=(11, 9), constrained_layout=True)
    ref=envelope(.25*raw)
    axes[0].plot((np.arange(len(ref))+.5)*.005-1.65, 20*np.log10(np.maximum(ref, 1e-12)), label='A raw reference x0.25')
    for folder, observation in zip(args.captures, observations):
        groups, mix, _, _, _=stereo_groups(folder)
        early=observation['start_frames'][1]/48000
        for key in ('continuous', 'events'):
            sf.write(args.output/(folder.name+'-'+key+'.wav'), groups[key], rate, subtype='FLOAT')
        env=envelope(mix)
        axes[0].plot((np.arange(len(env))+.5)*.005-early, 20*np.log10(np.maximum(env, 1e-12)), label=folder.name)
        if folder.name in ('original1', 'fixed1'):
            for key in ('continuous', 'events'):
                y=envelope(groups[key])
                axes[1].plot((np.arange(len(y))+.5)*.005-early, 20*np.log10(np.maximum(y, 1e-12)), label=folder.name+'/'+key)
        import csv
        with (folder/'telemetry.csv').open(encoding='utf-8', newline='') as stream:
            rows=list(csv.DictReader(stream))
        axes[2].plot([float(row['seconds'])-early for row in rows], [float(row['idle_weight']) for row in rows], label=folder.name)
    axes[0].set(ylabel='5ms RMS, dBFS', title='Acoustic marker alignment only; composite C demo, no measured RPM or matched-view timbre claim')
    axes[1].set(ylabel='5ms RMS, dBFS', title='Independent continuous/event outputs, including their signed cross-power in report')
    axes[2].set(ylabel='Idle replacement weight', xlabel='Seconds from early analysis marker / C early-event start')
    for ax in axes:
        ax.set_xlim(-.3, 2.7);ax.grid(alpha=.25);ax.legend(fontsize=8)
    axes[0].set_ylim(-75, -8);axes[1].set_ylim(-90, -10)
    figure.savefig(args.output/'handoff.png', dpi=140);plt.close(figure)
    write_json(args.output/'report.json', dict(schema='vsl.startup-handoff-observation/1',
        original_reference=provenance, original_reference_marker_bands=marker_bands(.25*raw,1.65), captures=observations,
        marker_gap_reference_seconds=.57, reference_marker_is_not_physical_timing=True,
        gain=.25, normalization=False, room_processing=False, listening_acceptance=False,
        inputs=[dict(path=str(path/'native.wav'), sha256=sha(path/'native.wav')) for path in args.captures]))
    print(json.dumps(observations, ensure_ascii=False), flush=True)


if __name__=='__main__':main()
