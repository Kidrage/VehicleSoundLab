"""Check E acoustic-family / display consistency and observe shift colour."""
import argparse
import json
from pathlib import Path
import sys

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--workspace', type=Path, required=True)
parser.add_argument('--observations', type=Path, required=True)
parser.add_argument('--out', type=Path, required=True)
args = parser.parse_args()
sys.path.insert(0, str(args.workspace / 'tools/python_deps'))
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from drive_evidence_v1.family import follow
from drive_evidence_v1.sources import sha

root = Path(__file__).resolve().parents[1]
annotation_path = root / 'research/drive_evidence_v1_annotations.json'
annotation = json.loads(annotation_path.read_text(encoding='utf-8'))
args.out.mkdir(parents=True, exist_ok=False)
data = np.load(args.observations / 'E_corsa_second_context/audio.npz')
times, hz = data['seconds'], data['hz']
power = data['psd_LR'].mean(axis=0)
family = follow(hz, times, power, 83.0, 94.01, 64.5, max_octaves_per_second=16)
assert family['status'] == 'connected_observed_family'
ft = np.array([r['seconds'] for r in family['rows']])
ff = np.array([r['reference_hz'] for r in family['rows']])
readings = []
for row in annotation['tach_intervals']:
    frequency = float(np.interp(row['seconds'], ft, ff))
    interval = row['rpm_interval']
    readings.append(dict(**row, acoustic_reference_hz=frequency,
        implied_order_interval=[60*frequency/interval[1], 60*frequency/interval[0]],
        hypotheses=[dict(order=order, implied_rpm=60*frequency/order,
                         inside_visual_interval=interval[0] <= 60*frequency/order <= interval[1])
                    for order in (1., 2.5, 5., 10.)]))
bands = data['band_power_LR'].mean(axis=0)
shifts = []
for row in annotation['gear_display_changes']:
    # Wide windows intentionally accommodate uncertain display lag. This is
    # a colour comparison, not a fitted cut/recovery envelope or clutch delay.
    lo, hi = row['last_old_seconds'], row['first_new_seconds']
    scope = (ft >= lo-.7) & (ft <= hi+.1)
    local_t = ft[scope]
    # A one-frame maximum derivative can select a brief mistracked line.
    # Require a decrease persisting in two separated100ms median windows.
    candidates = []
    for centre in local_t:
        pre_f = ff[(ft >= centre-.20) & (ft < centre-.10)]
        post_f = ff[(ft >= centre+.10) & (ft < centre+.20)]
        if len(pre_f) >= 9 and len(post_f) >= 9:
            candidates.append((float(np.median(post_f)/np.median(pre_f)), float(centre)))
    ratio, drop_time = min(candidates)
    assert ratio < .9, 'No persistent descent in this broad display context'
    before, after = [drop_time-.20, drop_time-.10], [drop_time+.10, drop_time+.20]
    pre = bands[:, (times >= before[0]) & (times < before[1])].mean(axis=1)
    post = bands[:, (times >= after[0]) & (times < after[1])].mean(axis=1)
    before_f = float(np.mean(ff[(ft >= before[0]) & (ft < before[1])]))
    after_f = float(np.mean(ff[(ft >= after[0]) & (ft < after[1])]))
    shifts.append(dict(display=row, acoustic_persistent_descent_centre_seconds=drop_time,
        audio_pre_window=before, audio_post_window=after,
        reference_hz_before=before_f, reference_hz_after=after_f,
        reference_ratio=after_f/before_f, band_post_minus_pre_db=(10*np.log10(post/pre)).tolist(),
        warning='80ms windows; audio/video clocks and cluster lag unmeasured. Not exact cut/recovery or torque timing.'))
support = np.array([r['independent_line_support'] for r in family['rows']])
result = dict(schema='vsl.drive-evidence-summary/1',
    observation_sha256=sha(args.observations / 'observations.json'), annotation_sha256=sha(annotation_path),
    family=family, visual_audio_readings=readings, shifts=shifts,
    hypothesis_visual_interval_counts={str(order):sum(r['hypotheses'][j]['inside_visual_interval'] for r in readings)
        for j, order in enumerate((1., 2.5, 5., 10.))},
    family_fraction_with_at_least_two_independent_lines=float(np.mean((support>0).sum(axis=1)>=2)),
    band_hz=[[28,120],[120,400],[400,1200],[1200,3000],[3000,8000],[8000,16000]],
    scope='E high-speed cabin only. A/B/D observations remain separate. No runtime/accepted source parameters changed.',
    limits=annotation['not_established'])
(args.out / 'report.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
fig, axes = plt.subplots(2, 1, figsize=(13, 7), sharex=True, constrained_layout=True)
axes[0].plot(ft, ff*24, label='Acoustic line /2.5 *60 (hypothesis)', lw=1)
for row in readings:
    low, high = row['rpm_interval']
    axes[0].errorbar(row['seconds'], (low+high)/2, yerr=(high-low)/2, fmt='o', color='#bb4b1d', ms=4)
axes[0].set_ylabel('RPM / broad display interval')
axes[0].set_title('E cabin: acoustic hypothesis and independent visual intervals; A/V delay unmeasured')
axes[0].legend()
axes[1].plot(ft, ff, label='Tracked acoustic family reference', lw=1)
axes[1].plot(times, data['strongest160_450_hz'], '.', ms=1, alpha=.4, label='Strongest peak (can switch lines)')
for row in shifts:
    lo, hi = row['display']['last_old_seconds'], row['display']['first_new_seconds']
    axes[1].axvspan(lo, hi, color='grey', alpha=.2)
    axes[1].axvline(row['acoustic_persistent_descent_centre_seconds'], color='#bb4b1d', alpha=.6, lw=.7)
axes[1].set_xlim(83.0, 94.05)
axes[1].set_ylabel('Observed Hz')
axes[1].set_xlabel('Source seconds; grey=gear-display bracket, red=persistent audio-descent diagnostic')
axes[1].legend()
fig.savefig(args.out / 'family_display.png', dpi=150)
plt.close(fig)
print(json.dumps(dict(readings=len(readings), hypothesis_counts=result['hypothesis_visual_interval_counts'],
    support=result['family_fraction_with_at_least_two_independent_lines'], shifts=[dict(gears=[s['display']['from'],s['display']['to']],time=s['acoustic_persistent_descent_centre_seconds'],ratio=s['reference_ratio']) for s in shifts])))
