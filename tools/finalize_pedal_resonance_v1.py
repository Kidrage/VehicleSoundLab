"""Check the pedal evidence, independently aggregate stems, and publish limits."""
import argparse
import csv
import hashlib
import json
import shutil
import sys
from pathlib import Path

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--workspace', type=Path, required=True)
p.add_argument('--verification', type=Path, required=True)
p.add_argument('--out', type=Path, required=True)
a = p.parse_args()
repo = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(a.workspace / 'tools/python_deps'))
import numpy as np
import soundfile as sf
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

sha = lambda path: hashlib.sha256(Path(path).read_bytes()).hexdigest()
v = json.loads(a.verification.read_text(encoding='utf-8'))
base = a.verification.parent
assert v['result'] == 'pedal_state_replay_technical_pass'
for name, digest in v['sources'].items():
    assert sha(repo/name) == sha(base/'exact_sources'/name) == digest, name
for name, digest in v['parameter_sha256'].items():
    assert sha(repo/name) == digest, name
for name, digest in v['evidence_sha256'].items():
    assert sha(base/name) == digest, name
for cmd in v['commands']:
    assert cmd['exit'] == 0 and sha(base/cmd['log']) == cmd['sha256']
build_log = (base/v['commands'][0]['log']).read_text(encoding='utf-8', errors='replace')
assert not any(s in build_log.lower() for s in ('warning c', 'error c', 'warning lnk', 'error lnk'))

folder = base/'pedals'
trace = np.genfromtxt(folder/'pedal_trace.csv', delimiter=',', names=True)
dna, rate = sf.read(folder/'dna_stem.wav', always_2d=True)
detail, rate2 = sf.read(folder/'detail_stem.wav', always_2d=True)
assert rate == rate2 == 48000
state = v['inspection']
life = np.repeat(trace['lifecycle'].astype(int), 240)[:state['frames']]
op = np.repeat(trace['operating'].astype(int), 240)[:state['frames']]
assert len(life) == len(dna) == len(detail)
errors = []
for group, values in [('lifecycle', life), ('running_operating', op)]:
    for index, (name, measured) in enumerate(state[group].items()):
        keep = values == index
        if group == 'running_operating':
            keep &= life == 4
        assert int(keep.sum()) == measured['frames'], (group, name)
        if keep.any():
            for key, stem in [('dna_rms', dna), ('detail_rms', detail)]:
                actual = float(np.sqrt(np.mean(stem[keep]**2)))
                error = abs(actual-measured[key])
                assert error < 1e-12, (name, key, actual, measured[key])
                errors.append(error)

# A separate scalar oracle checks every exported support value using actual
# smoothed root and anchor weights; these ratios remain engineering limits.
profile_root = v['parameter_sha256']['voices/exterior_anchors_v1/index.json']
index_model = json.loads((repo/'voices/exterior_anchors_v1/index.json').read_text())
root = index_model['voices'][0]['base_hz']
support_error = 0
for row in trace:
    ratio = row['root_hz']/root
    if ratio <= .9 or ratio >= 1.1:
        expected = 0
    elif ratio < .96:
        x = (ratio-.9)/.06
        expected = x*x*(3-2*x)
    elif ratio > 1.04:
        x = (1.1-ratio)/.06
        expected = x*x*(3-2*x)
    else:
        expected = 1
    if row['lower'] == row['upper']:
        weight = float(row['lower'] == 0)
    elif row['lower'] == 0:
        weight = 1-row['blend']
    elif row['upper'] == 0:
        weight = row['blend']
    else:
        weight = 0
    error = abs(expected*expected*weight-row['resonant_support'])
    assert error < 2e-14, (row['frame'], error)
    support_error = max(support_error, error)

a.out.mkdir(parents=True, exist_ok=False)
shutil.copy2(__file__, a.out/'executed_finalize.py')
with (base/'prior_C_index.csv').open(encoding='utf-8-sig') as f:
    rows = list(csv.DictReader(f))
assert len(rows) == 519
for row in rows:
    row['SHA-256'] = sha(repo/row['文件'])
roles = {'inspect.c': '非实时逐样本行程回放、避开内部切块的声层导出、状态能量及局部支持统计',
         'inspect.h': '离线踏板行程核查接口，不进入音频设备回调'}
for name, role in roles.items():
    file = 'experiments/drive_resonance_v1/'+name
    rows.append(dict(zip(rows[0], (file, '驾驶连续细节状态核查', 'VslDriveResonance_device', role, sha(repo/file)))))
assert len(rows) == 521
index = repo/'handoff/C文件索引.csv'
with index.open('w', encoding='utf-8-sig', newline='') as f:
    writer = csv.DictWriter(f, fieldnames=list(rows[0]), lineterminator='\n')
    writer.writeheader(); writer.writerows(rows)

plt.rcParams.update({'font.size': 10, 'axes.spines.top': False, 'axes.spines.right': False})
fig, axes = plt.subplots(3, 1, figsize=(10, 7.2), sharex=True, layout='constrained')
t = trace['seconds']
axes[0].plot(t, trace['rpm'], color='#183d68', linewidth=1.3)
axes[0].axhspan(root*120*.9, root*120*1.1, color='#dc9d30', alpha=.22,
               label='Local detail support (engineering mapping)')
axes[0].axhline(850, color='#717171', linewidth=.8, linestyle='--', label='Controller idle: 850 RPM')
axes[0].set_ylabel('Engineering RPM'); axes[0].legend(loc='upper right', fontsize=8)
axes[0].set_title('One driver: pedal acceleration, shifts, lift, braking and shutdown')
axes[1].plot(t, trace['resonant_support'], color='#bd6a12', label='Detail support (power weight)')
axes[1].plot(t, trace['dna_envelope'], color='#287c73', label='DNA envelope', alpha=.8)
axes[1].set_ylabel('Amount'); axes[1].legend(loc='upper right', fontsize=8)
axes[2].step(t, trace['gear'], where='post', color='#183d68', label='Actual gear')
axes[2].set_ylabel('Gear'); axes[2].set_xlabel('Time (s)'); axes[2].set_yticks(range(4))
for ax in axes:
    ax.grid(alpha=.18); ax.set_xlim(0, 16)
fig.savefig(a.out/'coverage.png', dpi=160)
shutil.copy2(a.out/'coverage.png', repo/'research/pedal_resonance_v1_coverage.png')
plt.close(fig)
summary = dict(schema='vsl.pedal-resonance-summary/1', result=v['result'], date='2026-11-12',
    C_H_rows=521, unchanged_prior_C_H=518, modified_prior_C_H=1, new_C_H=2,
    C_H_index_sha256=sha(index), existing_targeted_contracts_passed=1,
    current_full_suite_count=51, full_suite_not_repeated=True,
    frames=state['frames'], shifts=state['shifts'], overruns=state['overruns'],
    running_operating=state['running_operating'], device=v['pedals'],
    source_and_front_2_12_exact=True, independent_state_rms_max_error=max(errors),
    independent_support_max_error=support_error,
    stable_idle_detail_output=False, low_profile_base_hz=root,
    detail_support_engineering_rpm=[root*120*.9, root*120*1.1],
    controller_idle_engineering_rpm=850, controller_idle_acoustic_target_hz=850/120,
    parameter_index_sha256=profile_root, no_controller_or_parameter_changes=True,
    default_host_changed=False, new_listening_acceptance=False,
    full_idle_or_acceleration_timbre_calibrated=False, limits=v['limits'],
    evidence_sha256={str(a.verification.relative_to(a.workspace)).replace('\\','/'): sha(a.verification),
                     str((a.out/'coverage.png').relative_to(a.workspace)).replace('\\','/'): sha(a.out/'coverage.png')})
for target in (a.out/'summary.json', repo/'research/pedal_resonance_v1_summary.json'):
    target.write_text(json.dumps(summary, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
print(json.dumps(dict(result=summary['result'], C_H=521, rms_error=max(errors), support_error=support_error)))
