"""Independent edge degrees, track inheritance and reporting-only phase advance."""
import math
import statistics
from .wave import near

def audit_temporal(rows, actual, plan):
    frames, transitions, identity = [], [], 0
    dt = plan['hop'] / plan['sample_rate']
    for number, row in enumerate(rows):
        nodes = [dict(v) for v in row['lines'] if v['eligible']]
        inherited, edges = {}, []
        if number:
            for i, a in enumerate(frames[-1]):
                for j, b in enumerate(nodes):
                    forward = b['frequency_hz'] - a['frequency_hz'] - dt * a['chirp_hz_per_second']
                    backward = a['frequency_hz'] - b['frequency_hz'] + dt * b['chirp_hz_per_second']
                    difference = b['chirp_hz_per_second'] - a['chirp_hz_per_second']
                    if max(abs(forward), abs(backward)) <= .5 and abs(difference) <= 8:
                        edges.append(dict(previous=i, current=j, forward_error_hz=forward,
                                          backward_error_hz=backward, chirp_difference=difference))
            for edge in edges:
                i, j = edge['previous'], edge['current']
                if sum(v['previous'] == i for v in edges) == 1 and sum(v['current'] == j for v in edges) == 1:
                    inherited[j] = frames[-1][i]['track_id']
            observed = actual['transitions'][number - 1]
            assert observed['previous_window'] == number - 1 and observed['current_window'] == number
            assert len(observed['edges']) == len(edges)
            for expected, stored in zip(edges, observed['edges']):
                assert expected['previous'] == stored['previous'] and expected['current'] == stored['current']
                for key in ['forward_error_hz', 'backward_error_hz', 'chirp_difference']:
                    near(expected[key], stored[key])
            transitions.append(edges)
        for j, node in enumerate(nodes):
            if j in inherited:
                node.update(track_id=inherited[j], predecessor='unique', window=number)
            else:
                node.update(track_id=identity, predecessor='ambiguous' if any(v['current'] == j for v in edges) else 'none', window=number)
                identity += 1
        assert nodes == actual['frames'][number]
        frames.append(nodes)
    assert len(actual['transitions']) == max(0, len(rows) - 1) and len(actual['tracks']) == identity
    for k in range(identity):
        nodes = [v for frame in frames for v in frame if v['track_id'] == k]
        frequencies = [v['frequency_hz'] for v in nodes]
        chirps = [v['chirp_hz_per_second'] for v in nodes]
        label = 'unresolved'
        if len(nodes) >= 5:
            if max(map(abs, chirps)) <= .5:
                label = 'locally_stationary'
            elif statistics.median(map(abs, chirps)) >= 2 and max(frequencies) - min(frequencies) >= 1 and (min(chirps) > 0 or max(chirps) < 0):
                label = 'locally_moving'
        stored = actual['tracks'][k]
        assert stored == dict(track_id=k, windows=[v['window'] for v in nodes],
                              frequencies_hz=frequencies, chirps_hz_per_second=chirps, classification=label)
    count, maximum = 0, 0.
    for number, edges in enumerate(transitions, start=1):
        for edge in edges:
            i, j = edge['previous'], edge['current']
            if sum(v['previous'] == i for v in edges) != 1 or sum(v['current'] == j for v in edges) != 1:
                continue
            a, b = frames[number - 1][i], frames[number][j]
            stored = actual['phase_advance_diagnostics'][count]
            assert (stored['previous_window'], stored['current_window'], stored['track_id']) == (number - 1, number, a['track_id'])
            for key, f, q, sign in [('forward', a['frequency_hz'], a['chirp_hz_per_second'], 1),
                                    ('backward', b['frequency_hz'], b['chirp_hz_per_second'], -1)]:
                for c in range(2):
                    difference = (b['phase_at_midpoint_LR'][c] - a['phase_at_midpoint_LR'][c]) / (2 * math.pi)
                    residual = difference - dt * f - sign * .5 * q * dt * dt
                    value = (residual + .5) % 1 - .5
                    original = stored[key + '_residual_cycles_LR'][c]
                    error = abs(((value - original + .5) % 1) - .5)
                    assert error <= 1e-10
                    maximum = max(maximum, error)
            count += 1
    assert count == len(actual['phase_advance_diagnostics'])
    return dict(tracks=identity, phase_rows=count, maximum_phase_arithmetic_error=maximum)

def audit_predictions(rows, linked, actual):
    index, compared = 0, 0
    half = len(rows) // 2
    for track in linked['tracks']:
        nodes = [v for frame in linked['frames'] for v in frame if v['track_id'] == track['track_id']]
        if not nodes or nodes[0]['frequency_hz'] >= 200:
            continue
        item = actual[index]
        index += 1
        assert item['track_id'] == track['track_id'] and item['windows'] == track['windows']
        near(item['first_frequency_hz'], nodes[0]['frequency_hz'])
        train = [v for v in nodes if v['window'] < half and rows[v['window']]['guide_supported']]
        check = [v for v in nodes if v['window'] >= half and rows[v['window']]['guide_supported']]
        assert item['training_count'] == len(train) and item['check_count'] == len(check)
        if len(train) < 3 or len(check) < 3:
            assert item['status'] == 'insufficient'
            continue
        compared += 1
        assert item['status'] == 'compared'
        moving = statistics.median(v['frequency_hz'] / rows[v['window']]['ratio'] for v in train)
        fixed = statistics.median(v['frequency_hz'] for v in train)
        amp = [math.sqrt(math.fsum(v['amplitude_LR'][c] ** 2 for v in train) / len(train)) for c in range(2)]
        near(moving, item['training_moving_frequency_hz'])
        near(fixed, item['training_fixed_frequency_hz'])
        near(amp, item['training_amplitude_LR'])
        assert len(check) == len(item['check'])
        errors, ferr = [], dict(moving=[], fixed=[])
        for v, stored in zip(check, item['check']):
            assert v['window'] == stored['tile']
            for key, expected in [('moving', moving * rows[v['window']]['ratio']), ('fixed', fixed)]:
                value = v['frequency_hz'] - expected
                near(value, stored[key + '_frequency_error_hz'])
                ferr[key].append(abs(value))
            db = [20 / math.log(10) * (math.log(v['amplitude_LR'][c]) - math.log(amp[c])) for c in range(2)]
            near(db, stored['amplitude_error_db_LR'])
            errors.extend(map(abs, db))
        median = statistics.median(errors)
        near(median, item['median_absolute_amplitude_error_db'])
        for key in ['moving', 'fixed']:
            near(max(ferr[key]), item['maximum_frequency_error_hz'][key])
            assert item['diagnostic_targets_met'][key] == (max(ferr[key]) <= 4 and median <= 3)
    assert index == len(actual)
    return dict(low_start_tracks=index, compared_low_tracks=compared)
