"""Exercise the existing native host with pedals, then inspect owned-take replay.

No new RPM trajectory, parameter fit, controller, spatial model or listening gate.
"""
import argparse
import csv
import hashlib
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--workspace', type=Path, required=True)
p.add_argument('--build', type=Path, required=True)
p.add_argument('--out', type=Path, required=True)
a = p.parse_args()
repo = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(a.workspace / 'tools/python_deps'))
import numpy as np
import soundfile as sf

sha = lambda path: hashlib.sha256(Path(path).read_bytes()).hexdigest()
a.out.mkdir(parents=True, exist_ok=False)
r = dict(schema='vsl.pedal-resonance/1', result='running', commands=[], sources={})


def run(argv, timeout=120):
    start = time.perf_counter()
    proc = subprocess.run(list(map(str, argv)), cwd=repo, capture_output=True, timeout=timeout)
    log = a.out / f'command_{len(r["commands"]):02}.log'
    log.write_bytes(proc.stdout + proc.stderr)
    r['commands'].append(dict(argv=list(map(str, argv)), exit=proc.returncode,
                              seconds=time.perf_counter()-start, log=log.name, sha256=sha(log)))
    print(json.dumps(dict(command=str(argv[0]), exit=proc.returncode, log=str(log))), flush=True)
    assert proc.returncode == 0, (argv, log)
    return proc.stdout


try:
    index = repo / 'handoff/C文件索引.csv'
    shutil.copy2(index, a.out / 'prior_C_index.csv')
    with index.open(encoding='utf-8-sig') as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == 519
    changed = [v['文件'] for v in rows if sha(repo / v['文件']) != v['SHA-256']]
    assert changed == ['experiments/drive_resonance_v1/device.c'], changed
    r['prior_C_H'] = len(rows)
    r['unchanged_prior_C_H'] = len(rows)-len(changed)
    r['modified_prior_C_H'] = changed
    paths = [repo / v['文件'] for v in rows]
    paths += [repo / 'experiments/drive_resonance_v1' / v for v in ('inspect.c', 'inspect.h')]
    paths += [Path(__file__), repo / 'handoff/CMakeLists.txt']
    for path in paths:
        name = path.relative_to(repo).as_posix()
        frozen = a.out / 'exact_sources' / name
        frozen.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, frozen)
        r['sources'][name] = sha(path)
    r['parameter_sha256'] = {v.relative_to(repo).as_posix(): sha(v)
        for v in (repo / 'voices').rglob('*') if v.is_file()}
    run(['cmake', '--build', a.build, '--config', 'Release', '--target',
         'VslDriveResonance_device', '--parallel', '4'], timeout=300)
    shutil.copy2(a.build / 'CMakeCache.txt', a.out / 'CMakeCache.after_build.txt')
    for name in ('VslDriveResonance_device', 'VslAtlasTake_render'):
        path = a.build / 'bin/Release' / (name + '.exe')
        shutil.copy2(path, a.out / path.name)
    # These existing contracts cover the unchanged common-clock adapter/take.
    run(['ctest', '--test-dir', a.build, '-C', 'Release', '--output-on-failure',
         '-R', 'handoff_driving_resonant_detail_contract'], timeout=120)
    for name, flags in [('bench', []), ('pedals', ['--pedals'])]:
        folder = a.out / name
        folder.mkdir()
        run([a.out / 'VslDriveResonance_device.exe', folder, *flags])
        device = json.loads((folder / 'device.json').read_text())
        assert device['result'] == 'pass' and device['record_hash'] == device['play_hash']
        assert device['pedal_scenario'] == (name == 'pedals')
        r[name] = device
    folder = a.out / 'pedals'
    state = json.loads((folder / 'state_inspection.json').read_text())
    assert state['result'] == 'pass' and state['frames'] == 768123
    assert state['output_hash'] == r['pedals']['record_hash']
    assert sum(v['frames'] for v in state['lifecycle'].values()) == state['frames']
    assert sum(v['frames'] for v in state['running_operating'].values()) == state['lifecycle']['RUNNING']['frames']
    for name in ('IDLE', 'PULL', 'OVERRUN', 'SHIFT CUT', 'SHIFT RECOVER', 'REV MATCH'):
        assert state['running_operating'][name]['frames'] > 0, name
    assert state['lifecycle']['OFF']['frames'] > 0 and state['shifts'] >= 3
    assert all(v['mode'] == 1 for v in r['pedals']['controls'])  # VSL_PEDALS
    r['inspection'] = state
    recording, rate = sf.read(folder / 'recorded.wav', always_2d=True)
    inspected, rate2 = sf.read(folder / 'inspected.wav', always_2d=True)
    assert rate == rate2 == 48000 and recording.shape == (768123, 2)
    assert np.array_equal(recording, inspected)
    trace = np.genfromtxt(folder / 'pedal_trace.csv', delimiter=',', names=True)
    assert len(trace) == (state['frames']+239)//240
    detail, rate = sf.read(folder / 'detail_stem.wav', always_2d=True)
    dna, rate2 = sf.read(folder / 'dna_stem.wav', always_2d=True)
    assert rate == rate2 == 48000 and detail.shape == dna.shape == recording.shape
    assert np.isfinite(detail).all() and np.isfinite(dna).all() and np.any(detail != 0)
    # Stored state statistics must independently match the exported 200 Hz rows.
    for row in trace:
        if row['lifecycle'] == 4 and row['resonant_support'] == 0:
            assert np.array_equal(detail[int(row['frame'])], [0, 0])
    exports = []
    for channels in (2, 12):
        exports.append(json.loads(run([a.out / 'VslAtlasTake_render.exe',
            folder / 'detail_schema6.vslrun', folder / f'export_{channels}.wav', '--channels', channels])))
        assert exports[-1]['verified']
    stereo, rate = sf.read(folder / 'export_2.wav', always_2d=True)
    wide, rate2 = sf.read(folder / 'export_12.wav', always_2d=True)
    assert rate == rate2 == 48000 and np.array_equal(stereo, recording)
    assert np.array_equal(wide[:, :2], recording) and np.count_nonzero(wide[:, 2:]) == 0
    assert exports[0]['source_hash'] == exports[1]['source_hash'] == state['source_hash']
    r.update(result='pedal_state_replay_technical_pass', exports=exports,
        source_and_front_2_12_exact=True, no_controller_or_parameter_changes=True,
        new_listening_acceptance=False, full_idle_or_acceleration_timbre_calibrated=False,
        limits=['Synthetic pedal inputs, not physical pedal hardware or real-vehicle calibration',
                'Only one16smanual-shift scenario; neutral/auto/longrun/manual UI/physical7.1.4 not qualified',
                'Fixed low-detail support does not cover850engineeringRPM idle; no widening or remapping',
                'No new timbre fit, sound quality score or idle listening acceptance'])
except Exception as exc:
    r.update(result='failed', error=repr(exc))
    raise
finally:
    r['evidence_sha256'] = {v.relative_to(a.out).as_posix(): sha(v) for v in a.out.rglob('*')
                           if v.is_file() and 'exact_sources' not in v.parts}
    (a.out / 'report.json').write_text(json.dumps(r, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
