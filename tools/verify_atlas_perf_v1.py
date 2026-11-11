"""Verify preserved benchmark hashes, traces, and the accepted fixed DNA bytes."""
import argparse
import csv
import hashlib
import io
import json
from pathlib import Path
import shutil
import subprocess
import zipfile

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--workspace', type=Path, required=True)
parser.add_argument('--reference', required=True)
args = parser.parse_args()
repo = Path(__file__).resolve().parents[1]
root = args.workspace/'references/analysis/atlas_perf_v1'
out = root/'verification1'
out.mkdir(exist_ok=False)


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def rows(report):
    assert report['result'] == 'pass'
    return {(r['case'], r['repeat']): r for r in report['runs']}


baseline = read(root/'baseline1/report.json')
candidate = read(root/'candidate1/report.json')
old, new = rows(baseline), rows(candidate)
assert old.keys() == new.keys() and len(old) == 15
for key in old:
    for field in ('bank', 'mode', 'block', 'channels', 'capture', 'propagation',
                  'seconds', 'frames', 'blocks', 'output_hash', 'source_hash', 'shifts'):
        assert old[key][field] == new[key][field], (key, field)
for name, digest in candidate['source_sha256'].items():
    assert sha(repo/name) == sha(root/'candidate1/exact_sources'/name) == digest, name

trace_old = rows(read(root/'baseline2/report.json'))
trace_fields = ('frame', 'frames', 'root_hz', 'lower', 'upper', 'texture_updates')
trace_checks = []
for key, row in trace_old.items():
    name = f'{key[0]}_{key[1]}.csv'
    paths = [root/stage/name for stage in ('baseline2', 'candidate1')]
    assert sha(paths[0]) == row['trace_sha256']
    assert sha(paths[1]) == new[key]['trace_sha256']
    tables = []
    for path in paths:
        with path.open(newline='', encoding='utf-8') as stream:
            tables.append([tuple(r[k] for k in trace_fields) for r in csv.DictReader(stream)])
    assert tables[0] == tables[1], key
    trace_checks.append(dict(case=key[0], blocks=len(tables[0]), fields=trace_fields,
                             all_values_equal=True))

changed = {'modules/sound_dna/texture.c', 'modules/sound_dna/texture.h',
           'modules/dna_atlas/voice.c'}
revision = subprocess.check_output(['git', 'rev-parse', args.reference], cwd=repo, text=True).strip()
archive = subprocess.check_output(['git', 'archive', '--format=zip', revision], cwd=repo)
preserved, observed_changes = [], []
with zipfile.ZipFile(io.BytesIO(archive)) as files:
    for name in files.namelist():
        if Path(name).suffix not in ('.c', '.h'):
            continue
        equal = (repo/name).read_bytes() == files.read(name)
        if name in changed:
            assert not equal, name
            observed_changes.append(name)
        else:
            assert equal, name
            preserved.append(name)
assert set(observed_changes) == changed

accepted = read(repo/'research/coherent_low_v1_acceptance.json')
model = repo/'voices/dna_bank_v1/V10 Exterior.model'
assert sha(model) == accepted['dna_model_sha256']
assert sha(repo/accepted['model']) == accepted['model_sha256']
frozen = args.workspace/'baselines/atlas_realtime_v1'
manifest = read(frozen/'manifest.json')
old_probe = frozen/'bin/VslSoundDna_probe.exe'
entry = next(r for r in manifest['files'] if r['path'] == 'bin/VslSoundDna_probe.exe')
assert sha(old_probe) == entry['sha256']
(out/'bin').mkdir()
for name, probe in [('old', old_probe), ('new', repo/'handoff-build/bin/Release/VslSoundDna_probe.exe')]:
    frozen_probe = out/'bin'/(name+'.exe')
    shutil.copy2(probe, frozen_probe)
    command = [str(frozen_probe), str(model), str(out/(name+'.wav')), '8', '1', '1', '1']
    subprocess.run(command, cwd=repo, capture_output=True, check=True, timeout=90)
assert (out/'old.wav').read_bytes() == (out/'new.wav').read_bytes()

sources = {}
for name, digest in candidate['source_sha256'].items():
    path = repo/name
    target = out/'exact_sources'/name
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(path, target)
    sources[name] = digest
shutil.copy2(__file__, out/'executed_verify.py')
result = dict(schema='vsl.atlas-performance-verification/1', result='pass',
    benchmark_cases=15, output_and_source_fnv_hashes_match=True,
    trace_checks=trace_checks,
    existing_c_h=dict(reference_commit=revision, preserved=len(preserved), changed=sorted(changed)),
    accepted_models_unchanged=True,
    fixed_dna=dict(seconds=8, pitch=1, detail=1, raw=True,
        model_sha256=sha(model), wav_bytes_equal=True, wav_sha256=sha(out/'new.wav'),
        old_probe_sha256=sha(out/'bin/old.exe'), new_probe_sha256=sha(out/'bin/new.exe'),
        old_manifest_sha256=sha(frozen/'manifest.json')),
    source_sha256=sources, verifier_sha256=sha(__file__),
    limits=['Benchmark hashes are FNV, not a per-sample array comparison',
            'Fixed-DNA WAV equality is an actual complete file-byte comparison',
            'No subjective timbre improvement or hard realtime claim'])
(out/'verification.json').write_text(json.dumps(result, indent=2)+'\n', encoding='utf-8')
print(json.dumps(dict(result='pass', cases=15, trace_cases=len(trace_checks),
                     preserved_c_h=len(preserved), fixed_dna_wav_bytes_equal=True)))
