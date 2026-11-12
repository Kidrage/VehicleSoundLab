"""Audit the published startup action, acoustic bandwidth and later listening feedback."""
import argparse
import csv
import hashlib
import json
import shutil
import sys
from pathlib import Path


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--workspace', type=Path, required=True)
p.add_argument('--out', type=Path, required=True)
a = p.parse_args()
repo = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(a.workspace / 'tools/python_deps'))
import numpy as np
import soundfile as sf

a.out.mkdir(parents=True, exist_ok=False)
shutil.copy2(__file__, a.out / 'executed_audit.py')
root = a.workspace / 'references/analysis/catch_bloom_v1/render1/renders'
trace_path = root / '2_0.0_trace.csv'
with trace_path.open() as stream:
    rows = list(csv.DictReader(stream))
assert len(rows) == 1200
assert all(sha(root / f'2_{amount}_trace.csv') == sha(trace_path) for amount in ('0.5', '1.0'))
labels = ['OFF', 'READY', 'CRANK', 'CATCH', 'RUNNING', 'STOPPING']
transitions = []
last = None
for row in rows:
    state = int(row['lifecycle'])
    if state != last:
        transitions.append(dict(seconds=int(row['frame']) / 48000, state=labels[state],
                                controller_rpm=float(row['rpm']),
                                actual_OSC_acoustic_root_hz=float(row['root_hz'])))
        last = state
first = [r for r in rows if .15 <= int(r['frame']) / 48000 < 2.25]
phases = []
for state in (2, 3, 4):
    chosen = [r for r in first if int(r['lifecycle']) == state]
    peak = max(chosen, key=lambda r: float(r['rpm']))
    phases.append(dict(state=labels[state],
                       minimum_controller_rpm=min(float(r['rpm']) for r in chosen),
                       maximum_controller_rpm=float(peak['rpm']),
                       peak_seconds=int(peak['frame']) / 48000,
                       maximum_actual_OSC_root_hz=max(float(r['root_hz']) for r in chosen)))
assert phases[1]['maximum_controller_rpm'] == 1150
assert abs(phases[2]['minimum_controller_rpm'] - 850) < .001
base, rate = sf.read(root / '2_0.0_mix.wav', always_2d=True)
full, full_rate = sf.read(root / '2_1.0_mix.wav', always_2d=True)
assert rate == full_rate == 48000 and len(base) == len(full) == 288000
levels = []
for start, stop in ((0, 6), (.43, 1.08), (3.48, 4.13)):
    x = base[round(start * rate):round(stop * rate)]
    y = full[round(start * rate):round(stop * rate)]
    levels.append(dict(seconds=[start, stop],
                       full_mix_RMS_change_db=float(10 * np.log10(np.mean(y * y) / np.mean(x * x))),
                       delta_RMS_relative_to_base_db=float(10 * np.log10(np.mean((y - x)**2) / np.mean(x*x)))))
startup = (repo / 'voices/startup_settle_v1/A start cabin settle.model').read_text().splitlines()[0].split()
low = (repo / 'voices/exterior_anchors_v1/A Stationary Low.model').read_text().splitlines()[0].split()
startup_count, startup_root = int(startup[5]), float(startup[7])
low_count, low_root = int(low[5]), float(low[7])
assert startup_count == 256 and low_count == 288
paths = ['src/profiles/lifecycle.c', 'src/drive/lifecycle.c', 'src/core/profiles.c',
         'experiments/catch_bloom_v1/probe.c', 'modules/atlas_drive/render.c',
         'modules/dna_atlas/voice.c', 'modules/sound_residual/oscillator.c',
         'modules/residual_atlas/voice.c', 'tools/sound_dna/windowed.py',
         'voices/startup_settle_v1/A start cabin settle.model',
         'voices/exterior_anchors_v1/A Stationary Low.model',
         'voices/startup_detail_v1/A startup settling detail.residual']
report = dict(schema='vsl.startup-action-audit/1', date='2026-11-12',
              action='Two stationary engine starts, short running and shutdown; no accelerator blip or driving acceleration',
              driver_transitions=transitions, first_start_phases=phases,
              controller_policy=dict(crank_seconds=.28, crank_asymptote_rpm=220,
                                     catch_rise_seconds=.20, catch_settle_seconds=.45,
                                     flare_rpm=1150, idle_rpm=850),
              acoustic_mapping=dict(model_base_hz=startup_root, bound_controller_rpm=850,
                                    physical_RPM_or_engine_order_identified=False,
                                    meaning='Engineering playback binding only; do not interpret acoustic Hz as crank RPM'),
              representation_limits=dict(
                  startup_harmonics=startup_count, startup_steady_highest_line_hz=startup_count*startup_root,
                  stationary_low_harmonics=low_count, stationary_low_highest_line_hz=low_count*low_root,
                  startup_detail_band_hz=[300, 8000], general_detail_band_hz=[1200, 8000],
                  startup_detail_silent_band_hz=[600, 850],
                  caveat='Highest retained line is a representation ceiling, not guaranteed strong energy or a physical cutoff'),
              measured_levels=levels,
              user_feedback='差别不明显而且好像没那么好听。你知道这个声音模拟的是什么动作吗？你知道转速变化是多少吗？你目标模拟的转速变化是怎样的？',
              high_frequency_feedback='这套系统好像丢失了很多高频细节；要求说明高频模块、逼近实录的方法和真实可控范围。',
              listening_result='catch_bloom_improvement_not_accepted',
              target_reference='Approved A cabin start33..40s; exact RPM peak and time trajectory not established',
              inputs={str(path): sha(path) for path in [trace_path, root/'2_0.0_mix.wav', root/'2_1.0_mix.wav']},
              source_sha256={name: sha(repo/name) for name in paths},
              runtime_changed=False,
              limits=['Numerical RMS change does not contradict the human report of weak or worse perceptual change',
                      'A startup behaviour, real RPM trajectory, source separation and full high-frequency reproduction remain incomplete',
                      'This feedback does not reject the separately accepted fixed-context exterior coherent LF'])
(a.out / 'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n', encoding='utf-8', newline='\n')
print(json.dumps(dict(phases=phases, representation=report['representation_limits'],
                      feedback=report['listening_result']), ensure_ascii=False))
