"""Validate real device captures, source preservation and the native UI evidence."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workspace', type=Path, required=True)
    args = parser.parse_args()
    repository = Path(__file__).resolve().parents[1]
    workspace = args.workspace.resolve()
    sys.path.insert(0, str(workspace / 'tools/python_deps'))
    import numpy as np
    import soundfile as sf
    from PIL import Image
    output = workspace / 'references/analysis/scene_monitor_v1'
    device = output / 'verified_device'
    report_path = output / 'report.json'
    if report_path.exists():
        raise FileExistsError(report_path)
    device_report = json.loads((device / 'device.json').read_text())
    ui = json.loads((output / 'verified_ui/ui.json').read_text())
    assert device_report['result'] == ui['result'] == 'pass'
    assert device_report['device_muted'] and ui['device_muted']
    for name in ('baseline', 'live', 'stopped', 'restarted'):
        item = device_report[name]
        assert item['offline_float_equal'] and item['queue_empty'] == item['trace_overflow'] == 0
    assert ui['controls_isolated'] and ui['stop_restart_close'] and ui['model_bank_checked']

    def read(path):
        audio, rate = sf.read(path, always_2d=True, dtype='float32')
        assert rate == 48000 and audio.shape[1] == 2 and np.isfinite(audio).all()
        return audio

    baseline = read(device / 'baseline.wav')
    restart = read(device / 'restarted.wav')
    assert np.array_equal(restart, baseline[:len(restart)])
    acceptance = json.loads((repository / 'research/coherent_low_v1_acceptance.json').read_text(encoding='utf-8'))
    assert sha(repository / 'voices/dna_bank_v1/V10 Exterior.model') == acceptance['dna_model_sha256']
    assert sha(repository / acceptance['model']) == acceptance['model_sha256']
    reference = workspace / 'references/analysis/coherent_low_v1/audition/measured_mix.wav'
    assert sha(reference) == 'a3aa090f060c004738799d8a6d966a99d84bee1c45ce8f5b8ba6e104c66d9a7d'
    error = float(np.max(abs(baseline - read(reference)[:len(baseline)])))
    assert error <= 2 ** -22
    stopped = read(device / 'stopped.wav')
    trace = json.loads((device / 'stopped_controls.json').read_text())
    stop_at = trace['stop_frame']
    assert isinstance(stop_at, int) and stop_at > 240 and len(stopped) > stop_at + 480
    expected = baseline[:len(stopped)].astype('float64')
    envelope = np.maximum(0, 1 - (np.arange(len(stopped) - stop_at) + 1) / 480.)
    expected[stop_at:] *= envelope[:, None]
    assert np.array_equal(stopped, expected.astype('float32'))
    assert np.count_nonzero(stopped[-32:]) == 0
    live_trace = json.loads((device / 'live_controls.json').read_text())
    events = live_trace['events']
    assert len(events) == device_report['live']['applied_controls'] == 10
    assert events[0]['frame'] == 0 and all(a['frame'] < b['frame'] for a, b in zip(events, events[1:]))
    assert all(e['frame'] % 512 == 0 for e in events)
    image_path = output / 'verified_ui/ui.png'
    image = np.asarray(Image.open(image_path).convert('RGB'))
    assert image.shape == (710, 560, 3) and np.mean(np.any(image != 0, axis=2)) > .5
    source_files = []
    for directory in ['src', 'modules/sound_dna', 'modules/dna_scene', 'modules/scene_monitor', 'experiments/scene_monitor_v1']:
        source_files += [p for p in (repository / directory).rglob('*') if p.suffix in ('.c', '.h')]
    binaries = ['VslSceneMonitor.exe', 'VslSceneMonitor_device_verify.exe', 'VslSystem.exe']
    report = dict(schema='vsl.scene-monitor-evidence/1', device=device_report, ui=ui,
                  checks=dict(accepted_mix_hash_verified=True, default_mix_max_sample_error=error,
                              restart_bit_identical=True, stop_matches480_sample_envelope=True,
                              adopted_controls_persisted=True, screenshot_nonblack=True,
                              initial_hidden_screenshot_superseded=True),
                  source_sha256={str(p.relative_to(repository)).replace('\\', '/'): sha(p) for p in source_files},
                  binary_sha256={name: sha(repository / 'handoff-build/bin/Release' / name) for name in binaries},
                  source_base_revision=subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=repository, text=True).strip(),
                  status='Technical device/control checks passed; human listening and full driving integration remain open',
                  limitations=['Fixed V10 context; relative pitch0.90..1.10, not physical RPM',
                               'Warm/Hollow are synthetic fixtures, not other real-engine validations',
                               'UI tests are program-internal; no computer-use/manual pointer or keyboard verification',
                               'Device was submitted muted; captured pre-mute audio was checked numerically, not human-listened',
                               'Control evidence is a bounded debug trace, not the legacy driving take schema'])
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(dict(default_mix_max_sample_error=error, restart_equal=True, stop_equal=True,
                         controls=len(events), max_render_ms=max(device_report[k]['render_ms_max'] for k in ('baseline', 'live', 'stopped', 'restarted')))))


if __name__ == '__main__':
    main()
