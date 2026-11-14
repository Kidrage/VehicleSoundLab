"""One declared observed-peak anchor, without source-dependent rescue paths."""
import numpy as np
from drive_evidence_v1.family import peaks, follow


def anchor(observed, seconds):
    index = int(np.argmin(abs(observed['seconds']-seconds)))
    hz, prominence = peaks(observed['hz'], observed['power_low'][:, index])
    keep = (hz >= 100) & (hz <= 450)
    candidates = sorted(zip(hz[keep], prominence[keep]), key=lambda p: (-p[1], p[0]))
    return dict(frame_index=index, seconds=float(observed['seconds'][index]),
                candidates=[dict(hz=float(f), prominence_db=float(p)) for f, p in candidates],
                root_hz=float(candidates[0][0]/5) if candidates else None)


def track(observed, chosen, plan):
    if chosen['root_hz'] is None:
        return dict(status='no_anchor_peak', rows=[])
    return follow(observed['hz'], observed['seconds'], observed['power_low'],
                  *plan['source_seconds'], chosen['root_hz'],
                  reference_multiple=plan['reference_multiple'],
                  check_multiples=plan['check_multiples'],
                  max_octaves_per_second=plan['max_octaves_per_second'],
                  root_bounds=plan['root_bounds_hz'])
