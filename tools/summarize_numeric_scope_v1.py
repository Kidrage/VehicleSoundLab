"""Bind scoped numeric policy to sample fidelity, timing and actual device results."""
import argparse
import csv
import hashlib
import io
import json
from pathlib import Path
import subprocess
import zipfile

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--workspace', type=Path, required=True)
parser.add_argument('--reference', required=True)
args = parser.parse_args()
repo = Path(__file__).resolve().parents[1]
root = args.workspace/'references/analysis/numeric_scope_v1'


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


failed = read(root/'verification1/verification.json')
assert failed['result'] == 'failed' and 'at_take_commit' in failed['error']
verified = read(root/'verification2/verification.json')
paired = read(root/'paired1/report.json')
candidate = read(root/'candidate1/report.json')
assert verified['result'] == paired['result'] == candidate['result'] == 'pass'
assert paired['fidelity_sha256'] == sha(root/'verification2/verification.json')
assert paired['verifier_sha256'] == sha(repo/'tools/compare_numeric_scope_v1.py')
for report, directory in ((verified, 'verification2'), (candidate, 'candidate1')):
    for name, digest in report['source_sha256'].items():
        assert sha(repo/name) == sha(root/directory/'exact_sources'/name) == digest, name
stems = [s for r in verified['comparisons'] for s in r['stems']]
assert len(verified['comparisons']) == 6 and len(stems) == 156
assert all(r['complete_control_trace_bytes_equal'] for r in verified['comparisons'])
assert max(s['max_abs_error_fs'] for s in stems) <= verified['max_abs_sample_error_fs']
log = root/'ctest_LastTest.log'
text = log.read_text(encoding='utf-8', errors='replace')
assert text.count('Test Passed.') == 40 and 'Test Failed.' not in text
device = read(root/'device1/execution.json')
assert device['muted'] and device['monitor_exit_code'] == device['take_exit_code'] == 0
monitor = {name: read(root/'device1/monitor'/(name+'.json'))
           for name in ('bench', 'pedals', 'stopped', 'cabin_restart')}
assert all(r['muted'] and r['healthy'] and r['offline_float_equal'] for r in monitor.values())
take = read(root/'device1/recording.vslrun.json')
assert take['muted'] and take['verified'] and take['record_hash'] == take['play_hash']
exports = {str(ch): read(root/f'device1/render{ch}.json') for ch in (2, 12)}
assert all(r['verified'] for r in exports.values())
assert exports['2']['source_hash'] == exports['12']['source_hash']
assert exports['2']['audio_hash'] == take['record_hash']
with (repo/'handoff/C文件索引.csv').open(encoding='utf-8-sig', newline='') as stream:
    index = list(csv.DictReader(stream))
assert len(index) == 436
for row in index:
    assert sha(repo/row['文件']) == row['SHA-256'], row['文件']
revision = subprocess.check_output(['git','rev-parse',args.reference],cwd=repo,text=True).strip()
archive = subprocess.check_output(['git','archive','--format=zip',revision],cwd=repo)
changed = {'modules/atlas_drive/render.c', 'modules/atlas_monitor/render.c'}
preserved = []
with zipfile.ZipFile(io.BytesIO(archive)) as files:
    for name in files.namelist():
        if Path(name).suffix not in ('.c','.h'):
            continue
        equal = (repo/name).read_bytes() == files.read(name)
        if name in changed:
            assert not equal, name
        else:
            assert equal, name
            preserved.append(name)
assert len(preserved) == 431
sources = {row['文件']: row['SHA-256'] for row in index}
for name in ('handoff/CMakeLists.txt', 'handoff/tools/index_sources.py',
    'modules/atlas_drive/CMakeLists.txt', 'modules/atlas_take/CMakeLists.txt',
    'modules/rt_numeric/CMakeLists.txt', 'modules/rt_numeric/README.md',
    'research/numeric_scope_v1_plan.json', 'tools/verify_numeric_scope_v1.py',
    'tools/compare_numeric_scope_v1.py', 'tools/summarize_numeric_scope_v1.py', 'tools/freeze_numeric_scope_v1.py'):
    sources[name] = sha(repo/name)
evidence = {p.relative_to(root).as_posix(): sha(p) for p in sorted(root.rglob('*'))
            if p.is_file() and '__pycache__' not in p.parts}
summary = dict(schema='vsl.numeric-scope-summary/1', date='2026-11-12',
    technical_validation='pass', target='x64 Windows MSVC',
    policy='FTZ/DAZ scoped to atlas driving and monitor processing; complete incoming MXCSR restored',
    other_architectures='No-op; no optimization claim', hard_realtime_qualified=False,
    new_timbre_accepted=False, ctest=dict(passed=40, failed=0, log_sha256=sha(log)),
    c_h_files=436, existing_c_h=dict(reference_commit=revision, unchanged=431, changed=sorted(changed)),
    fidelity=dict(cases=6, stems=156, allowed_max_abs_error_fs=verified['max_abs_sample_error_fs'],
        measured_max_abs_error_fs=max(s['max_abs_error_fs'] for s in stems),
        changed_samples=sum(s['changed_samples'] for s in stems),
        complete_control_traces_bytes_equal=True,
        fixed_dna_whole_wav_bytes_equal=verified['fixed_dna_whole_wav_bytes_equal'],
        accepted_models_unchanged=verified['accepted_models_unchanged'],
        old_take_verified_by_frozen_player=verified['old_take_works_with_frozen_player'],
        new_player_rejects_old_identity=verified['new_player_rejects_old_identity']),
    performance=paired['comparisons'], monitor_device=monitor, take_device=take,
    take_exports=exports,
    failure='verification1 omitted mandatory frame0 event in the fixture; protocol correctly refused commit; fixture only corrected',
    limitations=['A5ms overruns persist; E had2 overruns in one other single-run capture case',
        'Short device runs and offline timing are not long-run qualification',
        'Rounding preservation checks do not imply audio identity between different rounding modes',
        'Driving stems have tiny numeric changes; no universal byte-equality claim',
        'Independent accepted fixed-context DNA/LF is not wide-RPM/state timbre acceptance',
        '12channel is offline technical evidence, not physical7.1.4 listening'],
    evidence_root=str(root), source_sha256=sources, evidence_sha256=evidence)
target = repo/'research/numeric_scope_v1_summary.json'
target.write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps(dict(path=str(target), ctest=40, fidelity=summary['fidelity'],
    performance=summary['performance'], evidence_files=len(evidence))))
