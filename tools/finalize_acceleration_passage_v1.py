"""Verify diagnostic inputs/outputs and publish a compact handoff summary."""
import argparse
import csv
import json
from pathlib import Path
import shutil
import sys

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--workspace', type=Path, required=True)
p.add_argument('--out', type=Path, required=True)
a = p.parse_args()
repo = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(a.workspace/'tools/python_deps'))
from drive_evidence_v1.sources import sha
from acceleration_passage_v1.evidence import read_json

a.out.mkdir(parents=True, exist_ok=False)
root = a.workspace/'references/analysis/acceleration_passage_v1'
report = read_json(root/'run1/report.json')
review = read_json(root/'review1/report.json')
assert report['result'] == 'current_C_source_diagnostic_pass_only'
assert review['result'] == 'review_technical_pass_only'
for name, digest in report['source_sha256'].items():
    assert sha(repo/name) == digest, name
    assert sha(root/'run1/exact_sources'/name) == digest, name
for name, digest in report['input_sha256'].items():
    assert sha(Path(name)) == digest, name
clock_root = a.workspace/'baselines/drive_evidence_v1/evidence/summary_v3'
clock_verification = read_json(clock_root/'verification.json')
assert clock_verification['result'] == 'pass'
assert sha(clock_root/'report.json') == clock_verification['summary_sha256']
for name, digest in report['output_sha256'].items():
    assert sha(root/'run1'/name) == digest, name
assert sha(root/'run1/state_passage_probe.exe') == report['probe_sha256']
for row in report['commands']:
    assert row['exit_code'] == 0 and sha(root/'run1'/row['log']) == row['sha256']
assert sha(root/'run1/report.json') == review['analysis_sha256']
for name, digest in review['source_sha256'].items():
    assert sha(repo/name) == sha(root/'review1/exact_sources'/name) == digest
for row in review['clips']:
    assert sha(root/'review1'/row['file']) == row['sha256']
assert sha(root/'review1/index.html') == review['page_sha256']
with (repo/'handoff/C文件索引.csv').open(encoding='utf-8-sig') as f:
    c_index = list(csv.DictReader(f))
assert len(c_index) == 478
for row in c_index:
    assert sha(repo/row['文件']) == row['SHA-256']
selection = repo/'voices/resonant_detail_v1/SELECTION.json'
held = read_json(selection)
assert held['preset'] == 'replace_35'
assert sha(selection.parent/held['profile']) == held['profile_sha256']
summary = dict(schema='vsl.acceleration-passage-summary/1',date='2026-11-12',
    result='existing_C_source_diagnostic_only',source='E',source_seconds=report['plan']['audio_seconds'],
    source_context='cabin fixed displayed gear5 rising displayed speed',
    approved_raw_sha256=report['provenance']['raw_sha256'],
    master_sha256=report['provenance']['master_sha256'],
    acoustic_root_endpoints_hz=report['acoustic_root_endpoints_hz'],
    measured_RPM=None,measured_load=None,original_phase_clock_qualification='not_passed_unchanged',
    context=report['context'],controls=report['controls'],traces=report['traces'],metrics=report['metrics'],
    selected_clock_rows=report['selected_clock_rows'],
    clock_rows_two_or_more_supports=report['clock_rows_two_or_more_supports'],
    source_training_overlap=True,new_timbre=False,human_accepted=False,runtime_changed=False,
    C_H_unchanged=478,Ctests_not_repeated=47,device_or_longrun_tests=False,
    new_review_files=len(review['clips']),review_URL=review['url'],HTTP_FFmpeg_JS_pass=True,
    manual_browser_interaction=False,manual_plot_and_three_existing_sheets_inspected=True,
    moving_selection_sha256=sha(selection),moving_selection_unchanged=True,
    idle_listening_still_pending=True,no_new_listening_question=True,
    frozen_clock_report_and_verification_link_pass=True,
    evidence_sha256={str(path.relative_to(a.workspace)).replace('\\','/'):sha(path)
                    for path in (root/'run1/report.json',root/'review1/report.json')},
    limits=report['limits'])
for path in (a.out/'report.json',repo/'research/acceleration_passage_v1_summary.json'):
    path.write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
shutil.copy2(__file__,a.out/'executed_finalize.py')
print(json.dumps(dict(result=summary['result'],C_H_unchanged=478,clips=summary['new_review_files'],review_URL=review['url'])))
