"""Bind the selected batch-only sources to performance and fidelity evidence."""
import argparse
import csv
import hashlib
import json
from pathlib import Path

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--workspace', type=Path, required=True)
args = parser.parse_args()
repo = Path(__file__).resolve().parents[1]
root = args.workspace/'references/analysis/atlas_perf_v1'


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


selected = read(root/'candidate1/report.json')
paired = read(root/'paired1/report.json')
verified = read(root/'verification1/verification.json')
device = read(root/'device1/recording.vslrun.json')
assert selected['result'] == paired['result'] == verified['result'] == 'pass'
assert device['verified'] and device['muted'] and device['record_hash'] == device['play_hash']
assert sha(root/'paired1/bin/new.exe') == selected['probe_sha256']
for name, digest in selected['source_sha256'].items():
    assert sha(repo/name) == sha(root/'candidate1/exact_sources'/name) == digest, name
log = root/'ctest_restored_batch_39.log'
log_bytes = log.read_bytes()
log_text = log_bytes.decode('utf-16' if log_bytes.startswith(b'\xff\xfe') else 'utf-8-sig')
assert '100% tests passed out of 39' in log_text
last_log = root/'ctest_restored_LastTest.log'
last_text = last_log.read_text(encoding='utf-8', errors='replace')
assert last_text.count('Test Passed.') == 39 and 'Test Failed.' not in last_text
with (repo/'handoff/C文件索引.csv').open(encoding='utf-8-sig', newline='') as stream:
    index = list(csv.DictReader(stream))
assert len(index) == 433
for row in index:
    assert sha(repo/row['文件']) == row['SHA-256'], row['文件']

sources = {p.relative_to(repo).as_posix(): sha(p)
           for folder in ('src', 'modules', 'experiments', 'tools', 'handoff/launcher')
           for p in sorted((repo/folder).rglob('*'))
           if p.is_file() and p.suffix in ('.c', '.h') and 'python_deps' not in p.parts}
for name in ('handoff/CMakeLists.txt', 'handoff/tools/index_sources.py',
             'tools/run_atlas_perf_v1.py', 'tools/compare_atlas_perf_v1.py',
             'tools/verify_atlas_perf_v1.py', 'tools/summarize_atlas_perf_v1.py',
             'tools/freeze_atlas_perf_v1.py'):
    sources[name] = sha(repo/name)
evidence = {p.relative_to(root).as_posix(): sha(p) for p in sorted(root.rglob('*'))
            if p.is_file() and '__pycache__' not in p.parts}
summary = dict(schema='vsl.atlas-performance-summary/1', date='2026-11-12',
    selected='batch_only', technical_validation='pass',
    hard_realtime_qualified=False, timbre_changed=False,
    accepted_fixed_models_unchanged=True, full_rpm_state_timbre_acceptance=False,
    ctest=dict(passed=39, failed=0, log_sha256=sha(log)),
    c_h_files=433, fidelity=verified,
    performance=dict(comparisons=paired['comparisons'], replicates=3,
                     all_output_and_source_hashes_match=True,
                     a_one_replicate_regressed=True,
                     scope='Normal-priority offline,16s,48kHz,240frame stereo,source capture enabled'),
    muted_short_device=device,
    rejected_cache=dict(stage='candidate2', reason='Output hashes matched; measured processing slowed',
                        live_cache_present=False),
    ftz_daz=dict(stage='numeric1', production_enabled=False,
                 scope='Unpaired diagnostic-only local MXCSR intervention; not qualification'),
    strict_recording_identity='Changed C updates renderer identity; preserve old frozen players',
    limitations=['5ms block overruns remain', 'Timing variability including one A regression',
                 'FNV comparison is not a per-sample array comparison',
                 'Short muted device checks are not long-run or listening acceptance',
                 '12channel is offline technical validation, not physical7.1.4 acceptance',
                 'exploration0 has no pre-execution source snapshot'],
    evidence_root=str(root), source_sha256=sources, evidence_sha256=evidence)
target = repo/'research/atlas_perf_v1_summary.json'
target.write_text(json.dumps(summary, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
print(json.dumps(dict(path=str(target), ctest=39, c_h_files=433,
                     evidence_files=len(evidence), comparisons=paired['comparisons'])))
