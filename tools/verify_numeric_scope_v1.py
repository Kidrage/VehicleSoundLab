"""Compare all generated stems, fixed accepted DNA and strict old-take identity."""
import argparse
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
sys.path.insert(0, str(args.workspace/'tools/python_deps'))
import numpy as np
import soundfile as sf


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


args.out.mkdir(parents=True, exist_ok=False)
plan_path = repo/'research/numeric_scope_v1_plan.json'
plan = read(plan_path)
frozen = args.workspace/'baselines/atlas_perf_v1'
manifest = read(frozen/'manifest.json')
expected = {r['path']: r['sha256'] for r in manifest['files']}
binary_sources = {
    'old_drive': frozen/'evidence/device1/bin/VslAtlasDrive_probe.exe',
    'old_take': frozen/'evidence/device1/bin/VslAtlasTake_render.exe',
    'old_fixed': frozen/'evidence/verification1/bin/new.exe',
    'new_drive': repo/'handoff-build/bin/Release/VslAtlasDrive_probe.exe',
    'new_take': repo/'handoff-build/bin/Release/VslAtlasTake_render.exe',
    'new_fixed': repo/'handoff-build/bin/Release/VslSoundDna_probe.exe',
    'checks': repo/'handoff-build/Release/VslNumericScope_checks.exe',
}
(args.out/'bin').mkdir()
binaries = {}
for label, path in binary_sources.items():
    if label.startswith('old_'):
        assert sha(path) == expected[path.relative_to(frozen).as_posix()]
    target = args.out/'bin'/(label+'.exe')
    shutil.copy2(path, target)
    binaries[label] = target
paths = [Path(__file__), plan_path, repo/'handoff/CMakeLists.txt']
for folder in ('src', 'modules', 'experiments'):
    paths += [p for p in sorted((repo/folder).rglob('*'))
              if p.is_file() and (p.suffix in ('.c', '.h') or p.name == 'CMakeLists.txt')]
paths += [p for p in sorted((repo/'voices').rglob('*')) if p.is_file()]
sources = {}
for path in paths:
    name = path.relative_to(repo).as_posix()
    target = args.out/'exact_sources'/name
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(path, target)
    sources[name] = sha(path)
metadata = dict(schema='vsl.numeric-scope-verification/1', result='running',
    reference_commit=manifest['source_commit'], old_manifest_sha256=sha(frozen/'manifest.json'),
    source_sha256=sources, binary_sha256={k: sha(v) for k, v in binaries.items()},
    plan_sha256=sha(plan_path), max_abs_sample_error_fs=plan['max_abs_sample_error_fs'])
(args.out/'metadata.json').write_text(json.dumps(metadata, indent=2)+'\n', encoding='utf-8')


def execute(name, command, expected_code=0):
    result = subprocess.run([str(x) for x in command], cwd=repo, capture_output=True,
                            text=True, encoding='utf-8', errors='replace', timeout=180)
    record = dict(command=[str(x) for x in command], exit_code=result.returncode,
                  expected_exit_code=expected_code, stdout=result.stdout, stderr=result.stderr)
    (args.out/(name+'_execution.json')).write_text(json.dumps(record, indent=2)+'\n', encoding='utf-8')
    assert result.returncode == expected_code, (name, result.stdout, result.stderr)
    return result


def run(case, label):
    voices = read(repo/'voices'/case['bank']/'index.json')['voices']
    models = [repo/'voices'/case['bank']/v['file'] for v in voices]
    for v, model in zip(voices, models):
        assert sha(model) == v['model_sha256']
    name = case['name']+'_'+label
    command = [binaries[label+'_drive'], *models[:2], args.out/name]
    for model in models[2:]:
        command += ['--anchor', model]
    for v in voices:
        command += ['--residual-anchor', repo/'voices/residual_atlas_v1'/(v['name']+'.residual')]
    command += ['--scenario', case['scenario'], '--seconds', case['seconds'], '--channels', case['channels'],
        '--events', '.2', '--detail', '1', '--gain', '.2', '--residual-gain', '.5',
        '--body-mix', '1', '--intake', '.5', '--mechanical', '.5', '--air', '.5',
        '--road', '.3', '--wind', '.3', '--spatial', '1', '--room', '.2']
    result = execute(name, command)
    print(name, result.stdout.strip(), flush=True)
    return name


try:
    execute('numeric_contract', [binaries['checks']])
    comparisons = []
    for case in plan['cases']:
        old, new = run(case, 'old'), run(case, 'new')
        paths = sorted(args.out.glob(old+'_*.wav'))
        stems = []
        for path in paths:
            suffix = path.name.removeprefix(old+'_')
            other = args.out/(new+'_'+suffix)
            a, ra = sf.read(path, always_2d=True)
            b, rb = sf.read(other, always_2d=True)
            assert ra == rb == 48000 and a.shape == b.shape
            assert np.isfinite(a).all() and np.isfinite(b).all()
            error = b-a
            maximum = float(np.abs(error).max())
            assert maximum <= plan['max_abs_sample_error_fs'], (case['name'], suffix, maximum)
            stems.append(dict(stem=suffix, samples=int(a.size), changed_samples=int(np.count_nonzero(error)),
                max_abs_error_fs=maximum, rms_error_fs=float(np.sqrt(np.mean(error*error))),
                complete_wav_bytes_equal=path.read_bytes() == other.read_bytes(),
                old_sha256=sha(path), new_sha256=sha(other)))
        assert len(stems) == 26
        trace_equal = (args.out/(old+'_trace.csv')).read_bytes() == (args.out/(new+'_trace.csv')).read_bytes()
        assert trace_equal, case['name']
        comparisons.append(dict(case=case, stems=stems, complete_control_trace_bytes_equal=True))
    acceptance = read(repo/'research/coherent_low_v1_acceptance.json')
    model = repo/'voices/dna_bank_v1/V10 Exterior.model'
    assert sha(model) == acceptance['dna_model_sha256']
    assert sha(repo/acceptance['model']) == acceptance['model_sha256']
    for label in ('old', 'new'):
        execute('fixed_'+label, [binaries[label+'_fixed'], model, args.out/('fixed_'+label+'.wav'), 8, 1, 1, 1])
    assert (args.out/'fixed_old.wav').read_bytes() == (args.out/'fixed_new.wav').read_bytes()
    old_take = frozen/'evidence/device1/recording.vslrun'
    assert sha(old_take) == expected[old_take.relative_to(frozen).as_posix()]
    old_result = execute('old_take_supported', [binaries['old_take'], old_take, args.out/'old_take.wav'])
    assert json.loads(old_result.stdout)['verified']
    execute('old_take_rejected_by_new_identity', [binaries['new_take'], old_take, args.out/'rejected.wav'], 3)
    assert not (args.out/'rejected.wav').exists()
    assert sha(old_take) == expected[old_take.relative_to(frozen).as_posix()]
    metadata.update(result='pass', comparisons=comparisons, fixed_dna_whole_wav_bytes_equal=True,
        accepted_models_unchanged=True, old_take_works_with_frozen_player=True,
        new_player_rejects_old_identity=True,
        limits=['Six explicit engineering drive passages, not full timbre/state acceptance',
                'Only current x64 Windows compiler/device target qualified',
                'Offline12channel comparison is not physical7.1.4 listening'])
except Exception as exc:
    metadata.update(result='failed', error=repr(exc))
    raise
finally:
    (args.out/'verification.json').write_text(json.dumps(metadata, indent=2)+'\n', encoding='utf-8')
print(json.dumps(dict(result='pass', cases=len(comparisons), stems=sum(len(r['stems']) for r in comparisons),
    max_abs_error_fs=max(s['max_abs_error_fs'] for r in comparisons for s in r['stems']),
    changed_samples=sum(s['changed_samples'] for r in comparisons for s in r['stems']))), flush=True)
