"""Audit direct moving-band FFT sums and publish the bounded deceleration result."""
import argparse
import csv
import json
from pathlib import Path
import shutil
import subprocess
import sys

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--workspace', required=True, type=Path)
args = parser.parse_args()
repo = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(args.workspace/'tools/python_deps'))
import numpy as np
from drive_evidence_v1.sources import read, sha

root = args.workspace/'references/analysis/cabin_decel_v1'
directories = ('exploration1', 'exploration2_four', 'exploration4_higher')
observations = {name: json.loads((root/name/'report.json').read_text(encoding='utf-8')) for name in directories}
verified = json.loads((root/'verification1/verification.json').read_text(encoding='utf-8'))
bands = json.loads((root/'band_power1/report.json').read_text(encoding='utf-8'))
for name, report, filename in [(n, r, 'report.json') for n, r in observations.items()] + [
    ('verification1', verified, 'verification.json'), ('band_power1', bands, 'report.json')]:
    for source, digest in report['source_sha256'].items():
        assert sha(root/name/'exact_sources'/source) == digest, (name, source)
assert bands['input_sha256'] == sha(root/'exploration1/report.json')
for name, digest in verified['input_sha256'].items():
    assert sha(root/name/'report.json') == digest
assert bands['known_control_passed'] and bands['maximum_control_error_db'] < .5
assert all(r['rejected'] for r in verified['missing_reference'])
assert all(not c['local_diagnostic_gate'] for r in observations.values() for c in r['cases'])

audio, provenance = read(args.workspace, 'E_corsa_first_context', 'cabin_dynamic_observation')
assert provenance == bands['provenance']
# Independently sum every physical window of the primary raw-band observation.
# Scalar FFT loop and explicit Hann/masks do not call the batched observer.
fft = 16384
size, hop = 3840, 240
window = .5-.5*np.cos(2*np.pi*np.arange(size)/size)
frequencies = np.arange(fft//2+1)*48000/fft
relative_bands = ((.5, 2.5), (2.5, 6.5), (6.5, 18.5), (18.5, 45.5), (45.5, 110.5), (110.5, 180.5))
errors = []
for observed, real in zip(observations['exploration1']['cases'], bands['cases']):
    seconds = real['case']['seconds']
    first = round((seconds[0]-.1-provenance['seconds'][0])*48000)
    stop = round((seconds[1]+.1-provenance['seconds'][0])*48000)
    fragment = audio[first:stop]
    start_seconds = provenance['seconds'][0]+first/48000
    rows = observed['references']['5']['tracking']['rows']
    times = np.array([r['seconds'] for r in rows]);roots = np.array([r['root_hz'] for r in rows])
    actual = []
    for start in range(0, len(fragment)-size+1, hop):
        center = start_seconds+(start+size/2)/48000
        if not seconds[0]+.04 <= center <= seconds[1]-.04:
            continue
        hz = np.interp(center, times, roots)
        z = np.fft.rfft(fragment[start:start+size]*window[:, None], fft, axis=0)
        power = abs(z)**2/(fft*np.sum(window**2));power[1:-1] *= 2
        actual.append(np.array([power[(frequencies >= lo*hz) & (frequencies < hi*hz)].sum(axis=0)
                                for lo, hi in relative_bands]).T)
    expected = next(r for r in real['observations'] if r['reference'] == 5 and r['scale'] == 1)
    assert len(actual) == expected['windows']
    error = float(abs(np.mean(actual, axis=0)-np.array(expected['power_LR'])).max())
    assert error < 1e-12
    errors.append(dict(case=real['case']['id'], windows=len(actual), maximum_absolute_error=error))

with (repo/'handoff/C文件索引.csv').open(encoding='utf-8-sig', newline='') as stream:
    index = list(csv.DictReader(stream))
assert len(index) == 421
for row in index:
    assert sha(repo/row['文件']) == row['SHA-256'], row['文件']
assert sha(repo/'handoff/C文件索引.csv') == verified['c_index_sha256']
previous_manifest = args.workspace/'baselines/shift_repeat_v1/manifest.json'
previous = json.loads(previous_manifest.read_text(encoding='utf-8'))
annotations = repo/'research/shift_repeat_v1_annotations.json'
assert sha(annotations) == next(r['sha256'] for r in previous['files'] if r['path'] == 'docs/shift_repeat_v1_annotations.json')
plot = repo/'research/cabin_decel_v1_clock.png'
shutil.copy2(root/'verification1/clock_and_colour.png', plot)

source_paths = [repo/'tools/explore_cabin_decel_v1.py', repo/'tools/verify_cabin_decel_v1.py',
                repo/'tools/analyze_decel_band_power_v1.py', Path(__file__), repo/'tools/freeze_cabin_decel_v1.py',
                repo/'research/cabin_decel_v1_plan.json', repo/'research/cabin_decel_v1_higher_carriers.json',
                *sorted((repo/'tools/cabin_decel_v1').glob('*.py'))]
evidence = sorted(p for p in root.rglob('*') if p.is_file() and '__pycache__' not in p.parts)
summary = dict(schema='vsl.cabin-deceleration-summary/1', date='2026-11-12',
    base_commit=subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=repo, text=True).strip(),
    evidence_root=str(root), provenance=provenance,
    phase_candidate_qualification='not_passed', raw_band_validation='pass',
    raw_band_validation_scope='Known spectral change and independent raw FFT arithmetic only; not complete state identification',
    phase_comparisons={name: [dict(case=c['case']['id'], gate=c['local_diagnostic_gate'],
        statuses={k: r['status'] for k, r in c['references'].items()},
        comparisons=[dict(reference=r['reference'], relative_root_p95=r['relative_root_p95'],
                           maximum_shape_db=r['maximum_400_8000_shape_db']) for r in c['comparisons']]) for c in report['cases']]
        for name, report in observations.items()},
    slow_controls=verified['fixtures'], missing_reference=verified['missing_reference'],
    common_source_center_checks=verified['common_interval_checks'],
    raw_band_shape_bands_relative_root=[[18.5, 45.5], [45.5, 110.5]],
    raw_band_shape_reference_relative_root=[6.5, 18.5],
    raw_band_cases=[{k: c[k] for k in ('case', 'primary_shape_db_LR', 'maximum_sensitivity_db',
                                     'sensitivity_min_db_LR', 'sensitivity_max_db_LR')} for c in bands['cases']],
    known_raw_controls=bands['known_controls'], independent_fft=errors,
    input_metadata_sha256={'references/segments_v1.json': provenance['catalog_sha256'],
        'references/approval_manifest.json': sha(args.workspace/'references/approval_manifest.json')},
    source_sha256={p.relative_to(repo).as_posix(): sha(p) for p in source_paths},
    evidence_sha256={p.relative_to(root).as_posix(): sha(p) for p in evidence},
    prior_visual_evidence_manifest_sha256=sha(previous_manifest), annotation_sha256=sha(annotations),
    c_index_sha256=sha(repo/'handoff/C文件索引.csv'), c_index_rows=len(index), plot_sha256=sha(plot),
    runtime_changes=False, new_models=False, new_state_mapping=False, human_accepted=False,
    limits=bands['limits'] + verified['limits'] + [
        'Narrow harmonic shape and wide raw bands measure different quantities; their errors are not comparable reproduction percentages',
        'Do not force total recorded power into DNA; preserve room/road/air/noise uncertainty and stereo observations'])
target = repo/'research/cabin_decel_v1_summary.json'
target.write_text(json.dumps(summary, ensure_ascii=False, indent=2)+'\n', encoding='utf-8', newline='\n')
print(json.dumps(dict(path=str(target), evidence_files=len(evidence), independent_fft=errors,
                      phase=summary['phase_candidate_qualification'], raw=summary['raw_band_validation']), ensure_ascii=False))
