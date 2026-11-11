"""Describe lifetimes in the accepted fitted model, not physical cylinders."""
from runtime_review import ROOT
import json
import math
import numpy as np


def main():
    out = ROOT/'references/analysis/reference_osc_v2'
    rows = {}
    with (out/'accepted64_high.model').open() as model, (out/'accepted64_high.ids').open() as ids:
        header = model.readline().split()
        rate, segments = int(header[2]), int(header[4])
        ids.readline()
        for _ in range(segments):
            start, frames, count = map(int, model.readline().split())
            assert [start, frames, count] == list(map(int, ids.readline().split()))
            identities = list(map(int, ids.readline().split()))
            assert len(identities) == count
            for identity in identities:
                line = model.readline().split()
                group, c = int(line[0]), list(map(float, line[1:]))
                row = rows.setdefault(identity, dict(group=group, seconds=0, amplitude_support=0,
                    first_sample=start, stop_sample=start+frames, min_hz=math.inf, max_hz=0))
                row['seconds'] += frames/rate
                row['stop_sample'] = start+frames
                # Expected sinusoidal power of a linear amplitude interval;
                # ignores phase interference. A salience proxy, not true energy.
                row['amplitude_support'] += sum(c[ch]**2+c[ch]*c[ch+1]+c[ch+1]**2 for ch in [0, 6])*frames/rate/12
                row['min_hz'] = min(row['min_hz'], c[3]/(2*math.pi))
                row['max_hz'] = max(row['max_hz'], c[3]/(2*math.pi))
    result = dict(scope='Parameter-domain observations of historical accepted64 model and its exterior-only HF addition. Not physical source/order/RPM identification.', groups={})
    for name, group in [('accepted_base', 0), ('added_high', 1)]:
        members = [(i, v) for i, v in rows.items() if v['group'] == group]
        total = sum(v['amplitude_support'] for _, v in members)
        result['groups'][name] = dict(track_count=len(members),
            track_lifetime_seconds_p50_p90=np.percentile([v['seconds'] for _, v in members], [50, 90]).tolist(),
            amplitude_support_fraction_on_tracks_lasting_at_least={str(t):sum(v['amplitude_support'] for _, v in members if v['seconds'] >= t)/total for t in [.1, .5, 1, 2]},
            most_salient_tracks=[dict(id=i, **v, amplitude_support_fraction=v['amplitude_support']/total) for i, v in sorted(members, key=lambda x:x[1]['amplitude_support'], reverse=True)[:12]])
    (out/'track_observations.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    for name, value in result['groups'].items():
        print(name, value['track_count'], value['track_lifetime_seconds_p50_p90'], value['amplitude_support_fraction_on_tracks_lasting_at_least'])


if __name__ == '__main__':
    main()
