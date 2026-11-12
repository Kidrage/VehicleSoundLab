"""Bind a source-only state diagnostic to C ownership and exact executed evidence."""
import argparse
import csv
import importlib.util
import json
from pathlib import Path

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--workspace', type=Path, required=True)
args = parser.parse_args()
repo = Path(__file__).resolve().parents[1]
import hashlib


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


root = args.workspace/'references/analysis/state_passage_v1'
report = json.loads((root/'run4/report.json').read_text(encoding='utf-8'))
assert report['result'] == 'source_host_technical_pass_only' and report['regression']['tests'] == 40
for name, digest in report['source_sha256'].items():
    assert sha(repo/name) == digest
    assert sha(root/'run4/exact_sources'/name) == digest
for name, digest in report['input_sha256'].items():
    assert sha(name) == digest, name
assert len(report['controls']) == 2 and report['invalid_trajectories_rejected_before_output'] == 6
assert not report['driver_state_calibrated'] and not report['human_accepted']
assert sha(root/'run4/state_passage_probe.exe') == report['probe_sha256']
index_path = repo/'handoff/C文件索引.csv'
with index_path.open(encoding='utf-8-sig', newline='') as stream:
    old = list(csv.DictReader(stream))
assert len(old) == 442
spec = importlib.util.spec_from_file_location('vsl_passage_index', repo/'handoff/tools/index_sources.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
rows = list(module.code_rows())
assert len(rows) == 445
mapping = {r[0]: r for r in rows}
for row in old:
    assert tuple(row.values()) == mapping[row['文件']], row['文件']
with index_path.open('w', encoding='utf-8-sig', newline='') as stream:
    writer = csv.writer(stream, lineterminator='\n')
    writer.writerow(old[0].keys())
    writer.writerows(rows)
summary = dict(schema='vsl.state-passage-summary/1', date='2026-11-12',
               result='source_diagnostic_only_not_full_state_calibration',
               final_run='run4', page=report['page'], prior442_C_H_unchanged=True,
               C_H_count=len(rows), new_C_H_count=3, c_index_sha256=sha(index_path),
               ctests=40, ctest_source='run2/command_02.log',
               independent_controls=report['controls'], rejected_invalid_trajectories=6,
               passages=report['passages'], source_only=True, driver_changes=False,
               models_changed=False, human_accepted=False, browser_interaction_checked=False,
               default_UI_changed=False, limitations=report['limits'],
               prior_attempts={'run1': '60s harness timeout; original report/source and failure supplement retained',
                               'run2': '40tests and all source/audio checks pass; original listening URLs retained',
                               'run3': 'Evidence reader expected an older CTest summary wording; assertion fails before rendering',
                               'run4': 'Current reproducible script; exact C/H and verified40test log reused, four review WAVs byte-equal to run2'},
               current_source_sha256={**report['source_sha256'],
                                      'tools/finalize_state_passage_v1.py': sha(__file__),
                                      'handoff/tools/index_sources.py': sha(repo/'handoff/tools/index_sources.py')},
               input_sha256=report['input_sha256'],
               evidence_sha256={p.relative_to(root).as_posix(): sha(p) for p in sorted(root.rglob('*'))
                                if p.is_file() and '__pycache__' not in p.parts})
(repo/'research/state_passage_v1_summary.json').write_text(
    json.dumps(summary, ensure_ascii=False, indent=2)+'\n', encoding='utf-8', newline='\n')
print(json.dumps(dict(C_H_count=len(rows), prior442_unchanged=True, result=summary['result'])))
