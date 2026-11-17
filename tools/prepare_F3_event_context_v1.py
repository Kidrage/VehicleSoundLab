"""Audit fixed candidate contrasts and declare the planned F3 visual shortlist."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import sys


def digest(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--scan', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--batch', choices=('first','remaining'), default='first')
    a = p.parse_args()
    sys.path.insert(0, 'E:/VehicleSoundLab/tools/python_deps')
    import numpy as np
    import soundfile as sf
    repo = Path(__file__).resolve().parents[1]
    plan_path = repo / 'research/F3_event_context_v1_plan.json'
    plan = json.loads(plan_path.read_text(encoding='utf-8'))
    scan = json.loads(a.scan.read_text(encoding='utf-8'))
    assert scan['source_id'] == plan['source'] == 'F3'
    assert scan['requested_ranges'] == plan['scan_seconds']
    assert digest(scan['source']) == scan['source_sha256']
    errors = []
    checked = []
    with sf.SoundFile(scan['source']) as stream:
        assert stream.samplerate == 48000 and stream.channels == 2
        def power(interval):
            first, last = [round(t * 48000) for t in interval]
            stream.seek(first)
            x = stream.read(last - first, dtype='float64', always_2d=True)
            assert len(x) == last - first and np.isfinite(x).all()
            # Independent channel dot products; no production measurement import.
            return sum(float(np.dot(x[:, c], x[:, c])) for c in range(2)) / (2 * len(x))
        for row in scan['candidates']:
            at = row['source_seconds']
            event = [at - .025, at + .075]
            backgrounds = dict(before=[at - .35, at - .15], after=[at + .16, at + .36])
            assert np.allclose(row['event_seconds'], event, rtol=0, atol=1e-12)
            for key, seconds in backgrounds.items():
                assert np.allclose(row[key + '_seconds'], seconds, rtol=0, atol=1e-12)
            ep = power(event)
            contrasts = {key: float(10 * np.log10(max(ep, 1e-30) / max(power(value), 1e-30)))
                         for key, value in backgrounds.items()}
            error = max(abs(contrasts[key] - row['contrast_db'][key]) for key in contrasts)
            errors.append(error)
            assert error < 1e-10
            assert row['both_full_band_above_3db'] == (min(contrasts.values()) >= 3)
            checked.append(dict(source_seconds=at, contrast_db=contrasts, max_error_db=error))
    qualified = sorted((r for r in scan['candidates']
                        if r['both_full_band_above_3db'] and r['source_seconds'] >= 80),
                       key=lambda r: r['minimum_contrast_db'], reverse=True)
    chosen = qualified[:8] if a.batch == 'first' else qualified[8:]
    cases = {}
    for index, row in enumerate(chosen):
        at = row['source_seconds']
        cases[f'F3_rank{index+1}_{round(at*1000)}'] = dict(
            source='F3', seconds=[at - 1, at + 1.5],
            frames=[at + d for d in (-.6, -.3, 0, .3, .6)], crop=[0., 0., 1., 1.],
            caption='Fixed both-background acoustic shortlist; inspect speech, cuts and actual driving context before fitting')
    at = plan['known_candidate_seconds']
    if a.batch == 'first':
        cases['F3_103_known'] = dict(source='F3', seconds=plan['inspection']['known_context_seconds'],
            frames=[103.0 + .1 * k for k in range(9)], crop=[0., 0., 1., 1.],
            caption='Known transient at103.465s; inspect stopped/first-gear context, not assumed afterfire')
    known = min(scan['candidates'], key=lambda r: abs(r['source_seconds'] - at))
    assert abs(known['source_seconds'] - at) < .01
    a.output.mkdir(parents=True, exist_ok=False)
    def save(name, value):
        (a.output / name).write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False), encoding='utf-8')
    save('contexts.spec.json', cases)
    save('report.json', dict(schema='vsl.F3-event-shortlist/1', result='passed',
        plan_sha256=digest(plan_path), scan_sha256=digest(a.scan),
        independent_contrast_checks=checked, maximum_error_db=max(errors),
        candidate_count=len(checked), both_background_qualified=sum(r['both_full_band_above_3db'] for r in scan['candidates']),
        qualified_after_80s=len(qualified), selected=chosen, known_candidate=known,
        fitting_performed=False, physical_identity_confirmed=False, goal_complete=False))
    shutil.copy2(__file__, a.output / 'executed_prepare.py')
    shutil.copy2(plan_path, a.output / plan_path.name)
    print(json.dumps(dict(candidate_count=len(checked), maximum_error_db=max(errors),
        selected=[{k:r[k] for k in ('source_seconds','minimum_contrast_db')} for r in chosen],
        known_contrast=known['contrast_db'])), flush=True)


if __name__ == '__main__':
    main()
