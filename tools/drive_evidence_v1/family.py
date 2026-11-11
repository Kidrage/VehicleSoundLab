"""Anchored multi-line acoustic family tracking; no physical order labels."""
import numpy as np
from scipy import signal


def peaks(hz, power):
    db = 10*np.log10(np.maximum(power, 1e-30))
    indices, properties = signal.find_peaks(db, prominence=4)
    keep = (hz[indices] >= 35) & (hz[indices] < 1200)
    indices, prominence = indices[keep], properties['prominences'][keep]
    a, b, c = db[indices-1], db[indices], db[indices+1]
    denominator = a-2*b+c
    delta = np.divide(.5*(a-c), denominator, out=np.zeros_like(a), where=abs(denominator)>1e-12)
    frequencies = hz[indices]+np.clip(delta, -.5, .5)*(hz[1]-hz[0])
    return frequencies, prominence


def follow(hz, times, power, start, stop, anchor_root, reference_multiple=5,
           check_multiples=(2, 3, 7), max_octaves_per_second=8):
    """DP among observed reference-line peaks; missing frames reject the path.

    Other line positions contribute their measured prominence. They do not
    create a reference line, fill gaps, or identify cylinders / physical RPM.
    """
    indices = np.flatnonzero((times >= start) & (times <= stop))
    nodes = []
    for i in indices:
        frequencies, prominence = peaks(hz, power[:, i])
        select = (frequencies/reference_multiple >= 20) & (frequencies/reference_multiple <= 90)
        roots = frequencies[select]/reference_multiple
        scores = np.clip(prominence[select], 0, 40)/40
        matched = []
        for root in roots:
            support = []
            for multiple in check_multiples:
                distance = abs(frequencies-multiple*root)
                k = int(np.argmin(distance))
                tolerance = max(6., .025*multiple*root)
                support.append(float(np.clip(prominence[k], 0, 40)/40) if distance[k] <= tolerance else 0.)
            matched.append(support)
        if len(roots):
            scores += np.sum(matched, axis=1)
        nodes.append(dict(root=roots, score=scores, matched=matched))
    if len(indices) < 3 or any(not len(n['root']) for n in nodes):
        return dict(status='no_connected_family', rows=[])
    initial = abs(np.log2(nodes[0]['root']/anchor_root))
    score = np.where(initial <= .10, nodes[0]['score']-(initial/.10)**2, -np.inf)
    links = []
    for j in range(1, len(nodes)):
        dt = times[indices[j]]-times[indices[j-1]]
        velocity = np.log2(nodes[j]['root'][:, None]/nodes[j-1]['root'][None, :])/dt
        cost = score[None, :]-.025*velocity**2
        cost[abs(velocity) > max_octaves_per_second] = -np.inf
        link = np.argmax(cost, axis=1)
        score = cost[np.arange(len(link)), link]+nodes[j]['score']
        links.append(link)
    if not np.isfinite(score).any():
        return dict(status='no_connected_family', rows=[])
    path = [int(np.argmax(score))]
    for link in reversed(links):
        path.append(int(link[path[-1]]))
    path.reverse()
    rows = [dict(seconds=float(times[i]), root_hz=float(node['root'][k]),
        reference_hz=float(node['root'][k]*reference_multiple),
        independent_line_support=node['matched'][k]) for i, node, k in zip(indices, nodes, path)]
    return dict(status='connected_observed_family', rows=rows,
        reference_multiple=reference_multiple, check_multiples=list(check_multiples),
        anchor_root_hz=anchor_root, max_octaves_per_second=max_octaves_per_second,
        warning='Acoustic-coordinate multipliers, not independently identified engine orders. Scores are diagnostics, not confidence probabilities.')
