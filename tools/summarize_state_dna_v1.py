"""Verify measurements and bind state evidence to current runtime boundaries."""
import argparse
import json
import hashlib
from pathlib import Path
import subprocess
import sys
import zipfile

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--workspace', type=Path, required=True)
args = parser.parse_args()
sys.path.insert(0, str(args.workspace/'tools/python_deps'))
import numpy as np
import soundfile as sf
from scipy import signal
from drive_evidence_v1.sources import sha
from state_dna_v1.review import write

repository = Path(__file__).resolve().parents[1]
root = args.workspace/'references/analysis/state_dna_v1'
observed = root/'observed_v2'
report = json.loads((observed/'report.json').read_text(encoding='utf-8'))
controls = json.loads((root/'controls_v2/verification.json').read_text(encoding='utf-8'))
budget = json.loads((root/'energy_budget/verification.json').read_text(encoding='utf-8'))
assert controls['result'] == budget['result'] == 'pass' and not report['human_accepted'] and not report['runtime_changed']
for r in (report, controls, budget):
    for name, expected in r['source_sha256'].items():
        assert sha(repository/name) == expected, name
probe = repository/'handoff-build/bin/Release/VslSoundDna_probe.exe'
assert sha(probe) == report['probe_sha256']
audio_checks = {}
for name, case in report['cases'].items():
    assert sha(observed/name/'voice.model') == case['model_sha256']
    assert sha(observed/name/'normalized_float.wav') == budget['observations'][name]['source_sha256']
    path = observed/name/'c_sustained_float.wav'
    assert sha(path) == case['render']['sha256']
    audio, rate = sf.read(path, always_2d=True)
    assert rate == 48000 and audio.shape == (8*48000, 2) and np.isfinite(audio).all()
    assert not np.array_equal(audio[:4*48000], audio[4*48000:])
    hz, power = signal.welch(audio, fs=rate, nperseg=48000, axis=0, detrend=False)
    reference = hz[(hz > 225) & (hz < 245)][np.argmax(power[(hz > 225) & (hz < 245)].mean(axis=1))]
    assert abs(reference-5*46.875) < 1
    fixed, _ = sf.read(observed/name/'normalized_float.wav', always_2d=True)
    def bands(data):
        f, p = signal.welch(data, fs=rate, nperseg=min(4096, len(data)), axis=0, detrend=False)
        return np.array([p[(f >= low) & (f < high)].sum(axis=0)*(f[1]-f[0])
            for low, high in [(28,120),(120,400),(400,1200),(1200,3000),(3000,8000),(8000,14000)]])
    audio_checks[name] = dict(peak=float(abs(audio).max()), finite=True, frames=len(audio), nonidentical_halves=True,
        strongest_reference_hz=float(reference), generated_minus_normalized_recording_db_LR=
        (10*np.log10((bands(audio)+1e-30)/(bands(fixed)+1e-30))).tolist(),
        warning='Short same-passage diagnostic; not held-out timbre acceptance')

review_path = root/'review/review.json'
if review_path.exists():
    review = json.loads(review_path.read_text(encoding='utf-8'))
    assert sha(review['page']) == review['page_sha256']
    for record in review['records']:
        assert sha(args.workspace/record['source']) == record['source_sha256']
        assert sha(args.workspace/record['file']) == record['sha256']
else:
    review = write(args.workspace, observed, report, root/'review')
    review_path.write_text(json.dumps(review, ensure_ascii=False, indent=2), encoding='utf-8')
qa_path = root/'review/browser_qa.json'
qa = json.loads(qa_path.read_text(encoding='utf-8'))
assert qa['result'] == 'pass' and qa['muted'] and qa['page_sha256'] == review['page_sha256']
assert qa['players'] == len(review['records']) and qa['no_autoplay'] and qa['one_player_at_a_time']

previous = args.workspace/'baselines/atlas_realtime_v1'
manifest = json.loads((previous/'manifest.json').read_text(encoding='utf-8'))
archive_path = previous/'source.zip'
assert sha(archive_path) == next(row for row in manifest['files'] if row['path']=='source.zip')['sha256']
tracked = subprocess.check_output(['git','ls-files','-z','--','*.c','*.h'], cwd=repository).decode().split('\0')
with zipfile.ZipFile(archive_path) as archive:
    for name in filter(None, tracked):
        assert sha(repository/name) == hashlib.sha256(archive.read(name)).hexdigest(), name
runtime_unchanged = dict(reference_commit=manifest['source_commit'], tracked_c_h_files=sum(bool(p) for p in tracked),
    all_bytes_equal=True, archive_sha256=sha(archive_path))

matched = []
for comparison in report['comparisons']:
    b = next(v for v in comparison['bins'] if v['root_bin_hz'] == [45,50])
    matched.append(dict(before=comparison['before'], after=comparison['after'], root_bin_hz=[45,50],
        correlated_window_counts=b['windows'],
        mean_root_hz=[next(v for v in report['cases'][n]['matched_bins'] if v['root_bin_hz']==[45,50])['mean_root_hz']
                      for n in (comparison['before'], comparison['after'])],
        **b['difference']))

catalog = json.loads((args.workspace/'references/segments_v1.json').read_text(encoding='utf-8'))
observations = json.loads((args.workspace/'references/analysis/drive_evidence_v1/observed/observations.json').read_text(encoding='utf-8'))
sources = {}
for source_id, source in catalog['sources'].items():
    assert source_id in ('A','B','D','E')
    for key in ('raw','master'):
        assert sha(args.workspace/source[key]) == source[key+'_sha256']
    sources[source_id] = dict(url=source['url'], raw_sha256=source['raw_sha256'], master_sha256=source['master_sha256'],
        video_available=bool(source['video']), observations=[key for key, val in observations['cases'].items()
            if val['provenance']['source'] == source_id],
        role={'A':'Stationary rear rising/falling colour; accepted moving-tailpipe context remains separate',
              'B':'Cabin stereo and dynamic audio; no inspected video or verified pedal/gear states',
              'D':'Enclosed dyno transitions; display labels/RPM not resolved',
              'E':'Cabin displayed upshifts and broad tach intervals; independent A/V latency unmeasured'}[source_id])

upstream = args.workspace/'references/analysis/coherent_low_v1/upstream'
runtime_paths = ['modules/dna_atlas/voice.c','modules/atlas_drive/render.c','src/drive/drive.c',
    'src/drive/shift.c','src/drive/fueling.c','src/core/orchestrator.c','src/profiles/voicing.c']
result = dict(schema='vsl.state-dna-summary/1', result='pass', runtime_changed=False, human_accepted=False,
    c_h_source_preservation=runtime_unchanged, browser_qa_sha256=sha(qa_path),
    production_state_atlas_ready=False, source_recordings=len(sources), sources=sources,
    controls=dict(null_max_band_error_db=controls['null_max_band_error_db'],
        known_colour_max_band_error_db=controls['known_colour_max_band_error_db'],
        drifting_clock_max_band_error_db=controls['drifting_clock_max_band_error_db']),
    window_energy_budget=dict(theoretical_white_noise_fraction=.375,
        measured_white_noise_fraction_LR=budget['known_white_noise']['projected_fraction_LR'],
        measured_coherent_tone_fraction_LR=budget['known_tone']['projected_fraction_LR'],
        real_3_8k_projected_minus_cell_db_LR={n:r['bands'][4]['projected_minus_cell_db_LR']
            for n,r in budget['observations'].items()},
        next_action='Extract omitted inter-harmonic energy as a separate source; do not apply8/3 power gain to full DNA.'),
    matched_root_observations=matched, c_audio_checks=audio_checks,
    independent_four_cycle_upper_bounds={n:c['nonoverlapping_four_cycle_window_upper_bound'] for n,c in report['cases'].items()},
    supported_hz_at_reference_root={n:c['supported_hz_at_reference_root'] for n,c in report['cases'].items()},
    upstream=dict(revision='ac2b37d8639027d79934a2023cf8d1d37d3b2f96',
        current_head_check='git ls-remote https://github.com/Kidrage/VehicleSoundSynth.git HEAD; same revision on2026-11-11',
        files={p.name:sha(p) for p in sorted(upstream.glob('*.maxpat'))},
        findings=['State/RPM owned by drivetrain', 'Separate post-module gains',
                  'steady/accel/decel times six pitch anchors; reference branch uses buffer/groove sample loops']),
    runtime_sha256={p:sha(repository/p) for p in runtime_paths},
    retained_runtime=dict(dna='RPM atlas and state gain envelope; no calibrated load/state spectral axis',
        events='Optional legacy procedural scheduler; not new measured backfire/intake/exhaust models',
        separate_lf_noise='Not yet attached to new driving chain; accepted LF is a different A moving-tailpipe context'),
    next_model_boundary='Preserve one OSC phase clock; separate RPM coordinate, state spectral shape, independent low/noise voices, and object spatial rendering',
    not_established=report['limits'], review=review,
    evidence_root=str(root), evidence_sha256={p.relative_to(root).as_posix():sha(p)
        for p in sorted(root.rglob('*')) if p.is_file() and p.name not in ('summary.json',)},
    source_sha256={p.relative_to(repository).as_posix():sha(p) for p in
        [Path(__file__), repository/'tools/run_state_dna_v1.py', repository/'tools/verify_state_dna_v1.py',
         repository/'tools/verify_dna_energy_budget_v1.py', repository/'tools/verify_state_dna_review_v1.cjs',
         repository/'tools/freeze_state_dna_v1.py', repository/'research/工况声纹分离V1.md',
         repository/'tools/explore_state_dna_v1.py', *repository.joinpath('tools/state_dna_v1').glob('*.py')]})
target = repository/'research/state_dna_v1_summary.json'
target.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps(dict(result='pass', source_recordings=len(sources), c_renders=len(audio_checks),
    production_state_atlas_ready=False, summary=str(target)), ensure_ascii=False))
