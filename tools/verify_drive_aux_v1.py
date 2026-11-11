"""Verify optional driving layers against frozen audio and layout invariants.

Writes a new evidence directory. No input recording/model is modified.
"""
import argparse
import csv
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--workspace', type=Path, required=True)
parser.add_argument('--out', type=Path, required=True)
args = parser.parse_args()
repo = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(args.workspace / 'tools/python_deps'))
import numpy as np
import soundfile as sf


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


args.out.mkdir(parents=True, exist_ok=False)
old_root = args.workspace / 'baselines/harmonic_body_v1'
manifest = json.loads((old_root / 'manifest.json').read_text(encoding='utf-8'))
old = old_root / 'bin/VslAtlasDrive_probe.exe'
assert sha(old) == next(r['sha256'] for r in manifest['files'] if r['path'] == 'bin/VslAtlasDrive_probe.exe')
current = repo / 'handoff-build/bin/Release/VslAtlasDrive_probe.exe'
runs = []


def run(name, bank, options, legacy=False):
    index = json.loads((repo / 'voices' / bank / 'index.json').read_text(encoding='utf-8'))
    voices = index['voices']
    for item in voices:
        assert sha(repo / 'voices' / bank / item['file']) == item['model_sha256']
    command = [str(old if legacy else current), str(repo / 'voices' / bank / voices[0]['file']),
               str(repo / 'voices' / bank / voices[1]['file']), str(args.out / name)]
    for item in voices[2:]:
        command += ['--anchor', str(repo / 'voices' / bank / item['file'])]
    for item in voices:
        command += ['--residual-anchor', str(repo / 'voices/residual_atlas_v1' / (item['name'] + '.residual'))]
    command += ['--gain', '.2', '--events', '.15', '--residual-gain', '.4', '--body-mix', '.6', *options]
    result = subprocess.run(command, cwd=repo, capture_output=True, text=True, encoding='utf-8', errors='replace')
    (args.out / (name + '_command.json')).write_text(json.dumps(dict(argv=command, returncode=result.returncode,
        stdout=result.stdout, stderr=result.stderr), ensure_ascii=False, indent=2), encoding='utf-8')
    assert result.returncode == 0, name
    report = json.loads((args.out / (name + '_report.json')).read_text(encoding='utf-8'))
    assert report['peak'] < .95
    runs.append(dict(name=name, binary_sha256=sha(old if legacy else current), **report))
    print(name, result.stdout.strip(), flush=True)


def audio(name, suffix):
    x, rate = sf.read(args.out / f'{name}_{suffix}.wav', always_2d=True)
    assert rate == 48000 and np.isfinite(x).all()
    return x


def trace(name):
    with (args.out / (name + '_trace.csv')).open(encoding='utf-8', newline='') as stream:
        return list(csv.DictReader(stream))


def raw_auxiliary(name):
    return np.column_stack([audio(name, 'aux_raw_' + suffix)[:, 0]
                            for suffix in ('intake', 'mechanical', 'air_left', 'air_right', 'road', 'wind')])


def common_trace_same(left, right):
    a, b = trace(left), trace(right)
    assert len(a) == len(b)
    assert all(all(x[k] == y[k] for k in x) for x, y in zip(a, b))


settings = {'A': ('exterior_anchors_v1', ['--scenario', 'shifts', '--seconds', '16']),
            'E': ('cabin_anchors_v1', ['--scenario', 'fixed', '--seconds', '6', '--rpm', '7600', '--load', '.8'])}
old_equal = {}
layers = ['--intake', '.5', '--mechanical', '.5', '--air', '.5', '--road', '.3', '--wind', '.3']
independent = ('dna_raw', 'dna', 'residual_raw', 'residual', 'harmonic_body_raw', 'harmonic_body', 'event_layer')
for context, (bank, options) in settings.items():
    old_name, zero, added = (context + '_' + suffix for suffix in ('old', 'zero', 'layers'))
    run(old_name, bank, options, True)
    run(zero, bank, options)
    suffixes = [p.name.removeprefix(old_name + '_').removesuffix('.wav') for p in sorted(args.out.glob(old_name + '_*.wav'))]
    for suffix in suffixes:
        assert np.array_equal(audio(old_name, suffix), audio(zero, suffix)), (context, suffix)
    common_trace_same(old_name, zero)
    assert not audio(zero, 'auxiliary').any() and raw_auxiliary(zero).any()
    old_equal[context] = suffixes
    run(added, bank, options + layers)
    for suffix in independent:
        assert np.array_equal(audio(zero, suffix), audio(added, suffix)), (context, suffix)
    assert np.array_equal(raw_auxiliary(zero), raw_auxiliary(added))
    assert trace(zero) == trace(added)
    expected = audio(zero, 'dry') + .2 * audio(added, 'auxiliary')
    assert float(abs(expected - audio(added, 'dry')).max()) < 1e-7
    assert np.array_equal(audio(added, 'dry'), audio(added, 'render'))
    assert not np.array_equal(audio(zero, 'render'), audio(added, 'render'))

bank, options = settings['A']
run('A_surround', bank, options + layers + ['--channels', '12', '--room', '.25'])
for suffix in independent + ('auxiliary', 'intake', 'mechanical', 'air_left', 'air_right', 'road', 'wind',
                              'exhaust_left', 'exhaust_right', 'body', 'events'):
    assert np.array_equal(audio('A_layers', suffix), audio('A_surround', suffix)), suffix
assert trace('A_layers') == trace('A_surround')
assert np.array_equal(raw_auxiliary('A_layers'), raw_auxiliary('A_surround'))

source = [Path(__file__), repo / 'handoff/CMakeLists.txt']
for folder in ('drive_aux', 'atlas_drive', 'atlas_take', 'atlas_take_io'):
    source += [p for p in sorted((repo / 'modules' / folder).iterdir()) if p.is_file()]
source += list(sorted((repo / 'experiments/drive_aux_v1').glob('*.[ch]')))
source += [repo / 'experiments/atlas_drive_v1/probe.c', repo / 'experiments/atlas_monitor_v1/ui.c',
           repo / 'experiments/atlas_monitor_v1/audio.c', repo / 'experiments/atlas_monitor_v1/audio.h',
           repo / 'experiments/atlas_take_v1/checks.c', repo / 'experiments/atlas_take_v1/device_checks.c']
snapshot = args.out / 'exact_sources'
for path in source:
    dest = snapshot / path.relative_to(repo)
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(path, dest)
result = dict(schema='vsl.driving-auxiliary-verification/1', result='pass', human_accepted=False,
              frozen_manifest_sha256=sha(old_root / 'manifest.json'), zero_equal_stems=old_equal,
              existing_sources_unchanged=True, common_controls_unchanged=True,
              auxiliary_raw_amount_independent=True, stereo_surround_sources_equal=True,
              runs=runs, source_sha256={p.relative_to(repo).as_posix(): sha(p) for p in source},
              limits=['Engineering auxiliary templates, not measured intake/mechanical/noise separation',
                      'A4/E2 sparse anchors and root/RPM hypotheses remain experimental',
                      'Fixed-context accepted moving A DNA/LF is not this driving atlas',
                      'No new listening, native UI visual, long-run realtime or physical7.1.4 acceptance'])
(args.out / 'verification.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print(json.dumps(dict(result='pass', old_equal_stems={k: len(v) for k, v in old_equal.items()},
                      layout_source_invariant=True), ensure_ascii=False), flush=True)
