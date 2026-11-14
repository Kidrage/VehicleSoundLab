"""Qualify two fixed B acoustic positions, saving exclusions without retuning."""
import argparse
from fractions import Fraction
import os
from pathlib import Path
import shutil
import subprocess
import sys

p = argparse.ArgumentParser(description=__doc__)
for key in ('workspace', 'out', 'dna-probe'):
    p.add_argument('--'+key, type=Path, required=True)
a = p.parse_args()
repo = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(a.workspace/'tools/python_deps'))
for key in ('OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS', 'OMP_NUM_THREADS'):
    os.environ[key] = '2'
import numpy as np
import soundfile as sf
from scipy import signal
from research_archive_v1 import load, save, sha
from drive_evidence_v1.sources import read
from shift_evidence_v1.spectrum import observe
from B_shift_voice_v1.selection import anchor, track
from decel_source_v1.aperture import extract
from decel_source_v1.checks import run as known_apertures
from sound_dna.windowed import estimate
from sound_dna.profile import export

a.out.mkdir(parents=True, exist_ok=False)
r = dict(result='running', sources={}, inputs={}, accepted=[], rejected=[])


def consume(path):
    r['inputs'][str(path)] = sha(path)
    return path


try:
    names = ['tools/run_B_shift_voice_v1.py', 'tools/B_shift_voice_v1/selection.py',
             'tools/drive_evidence_v1/sources.py', 'tools/drive_evidence_v1/family.py',
             'tools/shift_evidence_v1/spectrum.py', 'tools/decel_source_v1/aperture.py',
             'tools/decel_source_v1/checks.py', 'tools/exterior_clock_v1/warp.py',
             'tools/research_archive_v1.py', 'research/B_shift_voice_v1_plan.json',
             'research/B_shift_voice_v1_annotations.json']
    names += [v.relative_to(repo).as_posix() for v in (repo/'tools/sound_dna').glob('*.py')]
    for name in names:
        target = a.out/'exact_sources'/name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(repo/name, target)
        r['sources'][name] = sha(repo/name)
    plan = load(consume(repo/'research/B_shift_voice_v1_plan.json'))
    r['picture_clarification_before_source'] = load(consume(repo/'research/B_shift_voice_v1_annotations.json'))
    r['known_apertures_before_source'] = known_apertures(plan)
    # Exercise the actual observation/anchor/family chain before source reads.
    t = np.arange(2*48000)/48000
    known = sum(amp*np.cos(2*np.pi*40*k*t+.13*k) for k, amp in [(2,.02),(3,.03),(5,.2),(7,.025)])
    observed = observe(np.column_stack([known, .8*known]), 475, 80)
    chosen = anchor(observed, plan['anchor_seconds'])
    family = track(observed, chosen, plan)
    assert family['status'] == 'connected_observed_family'
    delta = max(abs(v['root_hz']-40) for v in family['rows'])
    assert delta < .1 and abs(chosen['root_hz']-40) < .1
    silence = observe(np.zeros((48000,2)), 475, 80)
    missing = track(silence, anchor(silence, plan['anchor_seconds']), plan)
    assert missing['status'] == 'no_anchor_peak'
    r['known_family_before_source'] = dict(root_error_hz=delta, rows=len(family['rows']),
        silent_status=missing['status'], scope='Constant known family plus missing-line rejection, not arbitrary dynamic-clock qualification')
    save(a.out/'report.json', r)
    audio, provenance = read(a.workspace, plan['source'], plan['use'])
    r['source'] = provenance
    assert provenance['seconds'] == plan['source_seconds']
    catalog = load(consume(a.workspace/'references/segments_v1.json'))
    for key in ('raw', 'master'):
        consume(a.workspace/catalog['sources']['B'][key])
    observed = observe(audio, provenance['seconds'][0], plan['window_ms'], hop=plan['hop'])
    np.savez_compressed(a.out/'observed.npz', **observed)
    chosen = anchor(observed, plan['anchor_seconds'])
    family = track(observed, chosen, plan)
    r['anchor'] = chosen
    r['family'] = family
    save(a.out/'report.json', r)
    if family['status'] != 'connected_observed_family':
        for case in plan['cases']:
            r['rejected'].append(dict(case=case, reason='One declared observed family failed; no alternate anchor/reference/window'))
    else:
        for number, case in enumerate(plan['cases']):
            folder = a.out/case['name']
            folder.mkdir()
            try:
                normalized, where, extraction = extract(audio, provenance['seconds'][0], family['rows'],
                                                         case['center_seconds'], plan)
            except ValueError as exc:
                row = dict(case=case, reason=str(exc), stage='aperture')
                r['rejected'].append(row)
                save(folder/'extraction.json', row)
                save(a.out/'report.json', r)
                continue
            sf.write(folder/'normalized.wav', normalized, 48000, subtype='FLOAT')
            np.savez_compressed(folder/'coordinates.npz', source_seconds=where)
            first, stop = [round((s-provenance['seconds'][0])*48000) for s in extraction['phase']['source_seconds']]
            sf.write(folder/'raw_source.wav', audio[first:stop], 48000, subtype='FLOAT')
            frames = len(range(0, len(normalized)-4096+1, 256))
            row = dict(case=case, **extraction, observation_frames=frames)
            minimum = min(v for values in extraction['heldout_coherence'].values() for v in values)
            passed = frames >= plan['gates']['minimum_observations'] and minimum > plan['gates']['heldout_carrier_coherence']
            save(folder/'extraction.json', row)
            if not passed:
                r['rejected'].append(dict(**row, reason='Original observation/heldout-carrier gate failed; no profile'))
            else:
                model, statistics = estimate(normalized, plan['harmonics'], plan['components'])
                root = extraction['root_hz']
                export(folder/'voice.model', model, root)
                ratio = Fraction(46.875/root).limit_denominator(10000)
                reference = signal.resample_poly(normalized, ratio.numerator, ratio.denominator, axis=0, window=('kaiser',8.6))
                sf.write(folder/'reference.wav', reference, 48000, subtype='FLOAT')
                consume(a.dna_probe)
                argv = list(map(str, [a.dna_probe, folder/'voice.model', folder/'DNA.wav', plan['seconds'], 1, 1, 1]))
                result = subprocess.run(argv, cwd=repo, capture_output=True, timeout=180)
                (folder/'C_render.log').write_bytes(result.stdout+result.stderr)
                row.update(statistics=statistics, resample_ratio=[ratio.numerator,ratio.denominator],
                           render_command=argv, render_exit_code=result.returncode)
                assert result.returncode == 0, result.stderr
                values, rate = sf.read(folder/'DNA.wav', always_2d=True)
                assert rate == 48000 and len(values) == plan['seconds']*48000 and np.isfinite(values).all()
                row.update(C_peak_FS=float(abs(values).max()), C_frames=len(values))
                r['accepted'].append(row)
                save(folder/'model.json', row)
            save(a.out/'report.json', r)
            print(dict(name=case['name'], root_hz=extraction['root_hz'],
                       heldout=extraction['heldout_coherence'], qualified=passed), flush=True)
    r.update(result='fixed_centers_checked', accepted_count=len(r['accepted']), rejected_count=len(r['rejected']),
             human_accepted=False, runtime_changed=False, physical_RPM_or_load=False,
             new_engines=0, room=False, recorded_timeline=False,
             scope='One-path local acoustic qualification, not generic clock/state or physical source separation')
except Exception as exc:
    r.update(result='failed', error=repr(exc))
    raise
finally:
    save(a.out/'report.json', r)
