"""Publish compact shift observations with hashes binding all retained attempts."""
import argparse
import json
from pathlib import Path
import subprocess
import sys

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--workspace', type=Path, required=True)
parser.add_argument('--out', type=Path, required=True)
args = parser.parse_args()
repo = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(args.workspace / 'tools/python_deps'))
import numpy as np
from drive_evidence_v1.sources import sha

assert not args.out.exists(), 'Preserve published summaries'
root = args.workspace / 'references/analysis/shift_evidence_v1'
report = json.loads((root / 'attempt4/report.json').read_text(encoding='utf-8'))
verification = json.loads((root / 'attempt4/verification.json').read_text(encoding='utf-8'))
assert verification['result'] == 'pass'
assert verification['report_sha256'] == sha(root / 'attempt4/report.json')
for name, expected in {**report['source_sha256'], **verification['source_sha256']}.items():
    assert sha(repo / name) == expected, name
for n in range(1, 5):
    previous = json.loads((root / f'attempt{n}/report.json').read_text(encoding='utf-8'))
    for name, expected in previous['source_sha256'].items():
        assert sha(root / 'versioned_sources' / f'attempt{n}' / name) == expected
baseline = report['analyses'][0]
assert baseline['window_ms'] == 80
def band_change(event, relative=False):
    prefix = 'relative_' if relative else ''
    pre = np.array(event[prefix + 'before']['power_LR']).mean(axis=0)
    post = np.array(event[prefix + 'after']['power_LR']).mean(axis=0)
    return (10 * np.log10(post / pre)).tolist()
events = [dict(gears=[e['display']['from'], e['display']['to']],
    marker_seconds=e['marker_seconds'], reference_ratio=e['ratio'],
    acoustic_25_75_seconds=e['acoustic_25_75_duration_seconds'],
    fixed_band_power_change_db=band_change(e), relative_band_power_change_db=band_change(e, True),
    pitch_matched_ascent_found=e['pitch_matched_ascent'] is not None) for e in baseline['events']]
markers = np.array([[e['marker_seconds'] for e in a['events']] for a in report['analyses']])
result = dict(schema='vsl.shift-evidence-published/1', date='2026-11-11', result='pass',
    base_commit=subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=repo, text=True).strip(),
    evidence_root=str(root), provenance=report['provenance'], band_hz=report['band_hz'],
    relative_bands=report['relative_clock_bands'], events=events,
    delay=baseline['delay'],
    short_window_note='40/60ms observed peaks are conditioned on80ms path, not independent continuous tracks',
    windows=[dict(window_ms=a['window_ms'], measured_peak_fraction=a['measured_peak_fraction'],
        two_other_line_support_fraction=a['fraction_two_independent_support_lines'],
        full_continuity_status=a['full_continuity_status']) for a in report['analyses']],
    maximum_marker_spread_seconds=float(np.ptp(markers, axis=0).max()),
    controls=verification['controls'],
    source_sha256={**report['source_sha256'], **verification['source_sha256'],
        **{p.relative_to(repo).as_posix():sha(p) for p in
           [Path(__file__), repo/'tools/freeze_shift_evidence_v1.py']}},
    evidence_sha256={p.relative_to(root).as_posix():sha(p) for p in sorted(root.rglob('*'))
                     if p.is_file() and '__pycache__' not in p.parts},
    runtime_changes=False, human_accepted=False, limits=report['limits'])
args.out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n')
print(json.dumps(dict(result='pass', events=len(events), marker_spread=result['maximum_marker_spread_seconds'],
    source_files=len(result['source_sha256']), evidence_files=len(result['evidence_sha256'])), ensure_ascii=False))
