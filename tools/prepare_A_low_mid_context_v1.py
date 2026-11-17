"""Audit every fixed A scan window, then shortlist original contexts by plan."""
import argparse
from pathlib import Path
import shutil

import numpy as np
import soundfile as sf

from research_archive_v1 import load, save, sha


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    out = parser.parse_args().output
    out.mkdir(parents=True, exist_ok=False)
    shutil.copy2(__file__, out/'executed_prepare.py')
    repo = Path(__file__).resolve().parents[1]
    root = Path('E:/VehicleSoundLab/references/analysis/event_full_envelope_v1')
    scan = load(root/'A-search1/report.json')
    plan = load(repo/'research/A_low_mid_event_search_v1_plan.json')
    assert scan['requested_ranges'] == plan['seconds']
    assert scan['source_id'] == 'A' and scan['detector']['family'] == plan['detector']
    assert sha(scan['source']) == scan['source_sha256']
    rows, errors = [], []
    with sf.SoundFile(scan['source']) as stream:
        assert stream.samplerate == 48000 and stream.channels == 2
        for row in scan['candidates']:
            powers = {}
            for name, offsets in [('event', (-.025, .075)), ('before', (-.35, -.15)), ('after', (.16, .36))]:
                first, last = [round((row['source_seconds']+v)*48000) for v in offsets]
                assert [round(v*48000) for v in row[name+'_seconds']] == [first, last]
                stream.seek(first)
                x = stream.read(last-first, dtype='float64', always_2d=True)
                assert len(x) == last-first and np.isfinite(x).all()
                powers[name] = sum(float(x[:, c] @ x[:, c]) for c in range(2))/(2*len(x))
            contrast = {name: float(10*np.log10(powers['event']/powers[name])) for name in ('before', 'after')}
            error = max(abs(contrast[name]-row['contrast_db'][name]) for name in contrast)
            assert error < 1e-10
            qualified = min(contrast.values()) >= 3
            assert qualified == row['both_full_band_above_3db']
            errors.append(error)
            rows.append(dict(source_seconds=row['source_seconds'], contrast_db=contrast,
                             minimum_contrast_db=min(contrast.values()), qualified=qualified))
    qualified = [row for row in rows if row['qualified'] and row['source_seconds'] >= 45]
    selected = sorted(qualified, key=lambda r: (-r['minimum_contrast_db'], r['source_seconds']))[:8]
    cases = {}
    for row in selected:
        at = row['source_seconds']
        name = 'A_low_mid_'+str(round(at*1000))
        cases[name] = dict(source='A', seconds=[at-1, at+1.5],
            frames=[at+delta for delta in (-.6, -.3, 0, .3, .6)], crop=[0., 0., 1., 1.],
            caption='Fixed low/mid detector candidate / view and action unclassified')
    save(out/'cases.json', cases)
    save(out/'report.json', dict(result='passed', source_sha256=scan['source_sha256'],
        scan_count=len(rows), qualified_count=sum(r['qualified'] for r in rows),
        maximum_power_contrast_error_db=max(errors), selected=selected, all_windows=rows,
        selection_plan_sha256=sha(repo/'research/A_low_mid_event_search_v1_plan.json'),
        physical_identity_confirmed=False, fitted=False, contexts_inspected=False))
    print(dict(result='passed', scanned=len(rows), selected=selected), flush=True)


if __name__ == '__main__':
    main()
