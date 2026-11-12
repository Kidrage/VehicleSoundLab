"""Render current C atlas on a qualified fixed-gear context, without new tuning."""
import argparse
import csv
import json
from pathlib import Path
import shutil
import subprocess
import sys

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--workspace', type=Path, required=True)
p.add_argument('--out', type=Path, required=True)
a = p.parse_args()
repo = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(a.workspace/'tools/python_deps'))
import numpy as np
import soundfile as sf
from scipy import signal
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from drive_evidence_v1.sources import read, sha
from acceleration_passage_v1.evidence import bind, read_json
from acceleration_passage_v1.diagnostics import compare, controls

a.out.mkdir(parents=True, exist_ok=False)
r = dict(schema='vsl.acceleration-passage/1', result='running', source_sha256={}, input_sha256={}, commands=[])


def command(argv):
    done = subprocess.run([str(v) for v in argv], cwd=repo, capture_output=True, timeout=60)
    log = a.out/f'command_{len(r["commands"]):02d}.log'
    log.write_bytes(done.stdout+done.stderr)
    r['commands'].append(dict(argv=[str(v) for v in argv], exit_code=done.returncode,
                              log=log.name, sha256=sha(log)))
    assert done.returncode == 0, (argv, log)
    return done


try:
    plan_path = repo/'research/acceleration_passage_v1_plan.json'
    plan = read_json(plan_path)
    paths = [Path(__file__), plan_path, repo/'tools/drive_evidence_v1/sources.py',
             repo/'tools/shift_evidence_v1/spectrum.py']
    for folder in ('tools/acceleration_passage_v1', 'experiments/state_passage_v1',
                   'modules/dna_atlas', 'modules/sound_dna', 'modules/harmonic_body'):
        paths.extend(v for v in (repo/folder).iterdir() if v.is_file())
    paths.extend(repo/v for v in ('src/io/file.c', 'src/io/file.h', 'src/io/wav.c', 'src/io/wav.h'))
    for path in paths:
        name = path.relative_to(repo)
        dest = a.out/'exact_sources'/name
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, dest)
        r['source_sha256'][name.as_posix()] = sha(path)
    rows, models, hashes, context = bind(a.workspace, repo, plan)
    r['input_sha256'].update(hashes)
    r['plan'], r['context'] = plan, context
    audio, provenance = read(a.workspace, plan['source_segment'], plan['source_use'])
    r['provenance'] = provenance
    r['controls'] = controls()
    start, stop = plan['audio_seconds']
    first, last = [round((v-provenance['seconds'][0])*48000) for v in (start, stop)]
    reference = audio[first:last]
    sf.write(a.out/'reference.wav', reference, 48000, subtype='FLOAT')
    selected = [v for v in rows if start-1e-8 <= v['seconds'] <= stop+1e-8]
    times = np.array([v['seconds'] for v in selected])
    roots = np.array([v['root_hz'] for v in selected])
    assert abs(times[0]-start) < 1e-8 and abs(times[-1]-stop) < 1e-8
    assert np.allclose(np.diff(times), .01, atol=1e-8, rtol=0)
    warmup = plan['warmup_frames']
    frames = np.r_[0, warmup+np.rint((times-start)*48000).astype(int)]
    values = np.r_[roots[0], roots]
    schedule = a.out/'trajectory.txt'
    schedule.write_text(''.join(f'{int(n)} {v:.17g}\n' for n, v in zip(frames, values)),
                        encoding='ascii', newline='\n')
    target = np.interp(np.arange(frames[-1]), frames, values)
    alpha = 1-np.exp(-1/(.018*48000))
    actual, _ = signal.lfilter([alpha], [1, -(1-alpha)], target, zi=[(1-alpha)*target[0]])
    build = repo/'build-acceleration-passage-v1'
    command(['cmake', '-S', repo/'experiments/state_passage_v1', '-B', build, '-A', 'x64'])
    command(['cmake', '--build', build, '--config', 'Release', '--parallel', '4'])
    probe = a.out/'state_passage_probe.exe'
    shutil.copy2(build/'Release/state_passage_probe.exe', probe)
    r['probe_sha256'] = sha(probe)
    generated = {}
    traces = {}
    for name, bank in (('single_anchor', models[:1]), ('two_anchors', models)):
        command([probe, schedule, a.out/f'{name}_warm.wav', a.out/f'{name}.csv',
                 plan['detail'], plan['seed'], plan['alignment_harmonics'], *bank])
        x, rate = sf.read(a.out/f'{name}_warm.wav', always_2d=True)
        assert rate == 48000 and x.shape == (frames[-1], 2) and np.isfinite(x).all()
        generated[name] = x[warmup:]
        assert generated[name].shape == reference.shape
        sf.write(a.out/f'{name}.wav', generated[name], 48000, subtype='FLOAT')
        trace = np.genfromtxt(a.out/f'{name}.csv', delimiter=',', names=True)
        at = trace['frame'].astype(int)
        follower_error = float(abs(trace['actual_acoustic_hz']-actual[at]).max())
        assert follower_error < 1e-10
        keep = at >= warmup
        traces[name] = dict(follower_oracle_error_hz=follower_error,
            pitch_target_error_rms_hz=float(np.sqrt(np.mean((actual[warmup:]-target[warmup:])**2))),
            pitch_target_error_max_hz=float(abs(actual[warmup:]-target[warmup:]).max()),
            telemetry_rows=int(keep.sum()), telemetry_colour_coverage_fraction=float(np.mean(trace['coverage'][keep] == 0)),
            peak_FS=float(abs(generated[name]).max()))
    metrics, observations = compare(reference, generated)
    delta = generated['two_anchors']-generated['single_anchor']
    r.update(metrics=metrics, traces=traces,
        anchor_morph_delta_RMS_FS=float(np.sqrt(np.mean(delta**2))),
        acoustic_root_endpoints_hz=[float(roots[0]), float(roots[-1])],
        acoustic_root_range_hz=[float(roots.min()), float(roots.max())],
        selected_clock_rows=len(selected),
        clock_rows_two_or_more_supports=sum(sum(v > 0 for v in row['independent_line_support']) >= 2 for row in selected),
        source_training_overlap=True, new_timbre=False, driving_state_validation=False,
        runtime_changed=False, human_timbre_accepted=False, C_H_unchanged=478, Ctests_not_repeated=47)
    fig, axes = plt.subplots(2, 1, figsize=(10, 7), constrained_layout=True)
    axes[0].plot(times, roots, label='Observed coarse acoustic coordinate')
    axes[0].plot(start+np.arange(len(reference))/48000, actual[warmup:], label='Actual C oscillator clock', alpha=.8)
    anchors = [float(path.read_text(encoding='ascii').splitlines()[0].split()[7]) for path in models]
    axes[0].axhspan(*anchors, color='green', alpha=.1, label='Two-anchor colour interval')
    axes[0].set(xlabel='Source seconds (AV offset unmeasured)', ylabel='Acoustic root Hz')
    axes[0].legend(fontsize=8)
    labels = [f'{lo:g}-{hi:g}' for lo, hi in metrics['bands_hz']]
    for name in generated:
        axes[1].plot(labels, np.mean(metrics['comparisons'][name]['mean_power_error_db_LR'], axis=1), 'o-', label=name)
    axes[1].axhline(0, color='gray', lw=.8)
    axes[1].set(xlabel='Raw fixed frequency bands Hz', ylabel='C minus mixed recording dB',
                title='DNA only; one seed; no per-file loudness compensation')
    axes[1].legend()
    fig.savefig(a.out/'diagnostics.png', dpi=140)
    plt.close(fig)
    r['output_sha256'] = {v.name: sha(v) for v in a.out.iterdir() if v.is_file() and v.suffix in ('.wav', '.csv', '.txt', '.png')}
    r['limits'] = plan['limits']+[
        'Pitch followers verify control operation, not inferred real engine timing or naturalness',
        'Colour clamps to endpoint outside fitted root interval; pitch itself is not clamped',
        'Same-source training overlap and one random seed are diagnostic, not held-out or statistical validation',
        'No new state voice fitted: quantitative deficits cannot all be assigned to one physical layer']
    r['result'] = 'current_C_source_diagnostic_pass_only'
except Exception as exc:
    r.update(result='failed', error=repr(exc))
    raise
finally:
    (a.out/'report.json').write_text(json.dumps(r, ensure_ascii=False, indent=2)+'\n', encoding='utf-8', newline='\n')
print(json.dumps({k:r[k] for k in ('result','acoustic_root_endpoints_hz','traces','metrics')}))
