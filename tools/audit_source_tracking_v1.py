"""Explain a fixed coarse-path rejection without changing or refitting it."""
import argparse
import json
from pathlib import Path
import shutil
import sys

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--workspace', type=Path, required=True)
parser.add_argument('--observed', type=Path, required=True)
parser.add_argument('--qualified', type=Path, required=True)
parser.add_argument('--out', type=Path, required=True)
args = parser.parse_args()
repo = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(args.workspace/'tools/python_deps'))
import numpy as np
from drive_evidence_v1.sources import sha
from state_colour_v2.clock import peaks, follow
from shift_evidence_v1.spectrum import observe
from stationary_dna_v1.fixtures import make

args.out.mkdir(parents=True, exist_ok=False)
report = dict(schema='vsl.source-tracking-audit/1', result='running', cases={}, sources={})
try:
    for source in (Path(__file__), repo/'tools/state_colour_v2/clock.py',
                   repo/'tools/shift_evidence_v1/spectrum.py', repo/'tools/stationary_dna_v1/fixtures.py',
                   repo/'tools/drive_evidence_v1/sources.py'):
        relative = source.relative_to(repo)
        target = args.out/'exact_sources'/relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        report['sources'][relative.as_posix()] = sha(source)
    qualified = json.loads((args.qualified/'report.json').read_text(encoding='utf-8'))
    observed = json.loads((args.observed/'report.json').read_text(encoding='utf-8'))
    assert qualified['observation_report_sha256'] == sha(args.observed/'report.json')
    report['qualification_report_sha256'] = sha(args.qualified/'report.json')
    for case in qualified['plan']['cases']:
        result = qualified['cases'][case['id']]
        assert result['local_diagnostic_gate'] is False
        directory = args.observed/case['observation']
        file = directory/f"observations_{case['window_ms']}ms.npz"
        assert sha(file) == result['input_observation_sha256']
        with np.load(file, allow_pickle=False) as archive:
            hz, times, power = [archive[key] for key in ('hz', 'seconds', 'power_low')]
        chosen = np.flatnonzero((times>=case['seconds'][0]-1e-8) & (times<=case['seconds'][1]+1e-8))
        item = dict(measured_frames=len(chosen), references={})
        for reference in [case['primary_reference'], *case['comparison_references']]:
            missing, nearby_missing, counts = [], [], []
            for index in chosen:
                frequencies, _ = peaks(hz, power[:, index])
                roots = frequencies/reference
                roots = roots[(roots>=15) & (roots<=80)]
                counts.append(len(roots))
                if not len(roots):
                    missing.append(float(times[index]))
                if not np.any(abs(np.log2(roots/case['initial_root_hz']))<=.12):
                    nearby_missing.append(float(times[index]))
            path = result['references'][str(reference)]['tracking']
            item['references'][str(reference)] = dict(existing_status=path['status'],
                no_candidate_frames=len(missing), no_candidate_seconds=missing,
                no_candidate_near_initial_root_frames=len(nearby_missing),
                no_candidate_near_initial_root_seconds=nearby_missing,
                candidate_count_quantiles=np.percentile(counts, [0, 50, 100]).tolist())
        # An independently generated signal diagnoses software scope only.
        # Its truth is never used to fill any source observations.
        reference = case['primary_reference']
        audio, _, _ = make(case['initial_root_hz'], reference, 'steady', seconds=3)
        fixture = observe(audio, 0, case['window_ms'])
        path = follow(fixture['hz'], fixture['seconds'], fixture['power_low'], .2, 2.8,
                      case['initial_root_hz'], reference)
        item['known_stationary_control'] = dict(root_hz=case['initial_root_hz'], reference=reference,
            source_seconds=[.2, 2.8], status=path['status'], rows=len(path['rows']),
            scope='Coarse tracking diagnostic only, not complete phase/profile validation or vehicle audio')
        report['cases'][case['id']] = item
        print(json.dumps(item), flush=True)
    report.update(result='audited_without_retry', model_exported=False, runtime_modified=False,
        limits=['No new interval, reference, window size, interpolation, threshold or source coordinate',
                'Candidate availability does not prove a unique or physical engine clock'])
except Exception as exc:
    report.update(result='failed', error=repr(exc))
    raise
finally:
    (args.out/'report.json').write_text(json.dumps(report, indent=2)+'\n', encoding='utf-8')
