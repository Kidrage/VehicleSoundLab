"""Observed native inventory initialization, original fitting/linking, phase reports."""
import numpy as np
from accel_ridges_v1.observe import associate
from accel_chirp_v1.fit import fit
from low_chirp_v1.link import link

def initial_graphs(inventories, ratios, ridge_plan):
    out = []
    for i, current in enumerate(inventories):
        neighbors = [j for j in [i - 1, i + 1] if 0 <= j < len(inventories)]
        graphs = {str(j): associate(current['hz'], inventories[j]['hz'], ratios[j] / ratios[i], 4., ridge_plan) for j in neighbors}
        q = []
        for k in range(len(current['hz'])):
            used = [j for j in neighbors if graphs[str(j)]['state'][k] == 'unique']
            def f(j):
                return inventories[j]['hz'][graphs[str(j)]['chosen'][k]]
            q.append((f(i + 1) - f(i - 1)) / .5 if len(used) == 2 else
                     (f(used[0]) - current['hz'][k]) / ((used[0] - i) * .25) if used else 0.)
        out.append(dict(neighbor_graphs=graphs, initial_chirp=q))
    return out

def fit_tile(audio, inventory, initialization, fit_plan):
    nominal = np.array(inventory['bin']) * 4.
    result, arrays = fit(audio, nominal, initialization['initial_chirp'], fit_plan)
    for i, line in enumerate(result['lines']):
        line.update(native_inventory_index=i, native_bin=inventory['bin'][i], native_peak_hz=inventory['hz'][i])
    return result, arrays

def temporal(rows, link_plan):
    result = link(rows, link_plan)
    phase_rows = []
    step = link_plan['hop'] / link_plan['sample_rate']
    def wrap(value):
        return ((value + .5) % 1.) - .5
    for transition in result['transitions']:
        previous = result['frames'][transition['previous_window']]
        current = result['frames'][transition['current_window']]
        for edge in transition['edges']:
            i, j = edge['previous'], edge['current']
            if sum(v['previous'] == i for v in transition['edges']) != 1 or sum(v['current'] == j for v in transition['edges']) != 1:
                continue
            a, b = previous[i], current[j]
            assert a['track_id'] == b['track_id']
            delta = (np.asarray(b['phase_at_midpoint_LR']) - a['phase_at_midpoint_LR']) / (2 * np.pi)
            forward = delta - (a['frequency_hz'] * step + .5 * a['chirp_hz_per_second'] * step * step)
            backward = delta - (b['frequency_hz'] * step - .5 * b['chirp_hz_per_second'] * step * step)
            phase_rows.append(dict(previous_window=transition['previous_window'], current_window=transition['current_window'],
                track_id=a['track_id'], forward_residual_cycles_LR=wrap(forward).tolist(),
                backward_residual_cycles_LR=wrap(backward).tolist()))
    result['phase_advance_diagnostics'] = phase_rows
    return result

def predictions(rows, linked):
    half = len(rows) // 2
    out = []
    for track in linked['tracks']:
        identity = track['track_id']
        nodes = [node for frame in linked['frames'] for node in frame if node['track_id'] == identity]
        if not nodes or nodes[0]['frequency_hz'] >= 200:
            continue
        train = [v for v in nodes if v['window'] < half and rows[v['window']]['guide_supported']]
        check = [v for v in nodes if v['window'] >= half and rows[v['window']]['guide_supported']]
        item = dict(track_id=identity, windows=track['windows'], first_frequency_hz=nodes[0]['frequency_hz'],
                    training_count=len(train), check_count=len(check), status='insufficient')
        if len(train) >= 3 and len(check) >= 3:
            moving = float(np.median([v['frequency_hz'] / rows[v['window']]['ratio'] for v in train]))
            fixed = float(np.median([v['frequency_hz'] for v in train]))
            amp = np.sqrt(np.mean([np.asarray(v['amplitude_LR']) ** 2 for v in train], axis=0))
            errors = [dict(tile=v['window'], moving_frequency_error_hz=v['frequency_hz'] - moving * rows[v['window']]['ratio'],
                fixed_frequency_error_hz=v['frequency_hz'] - fixed,
                amplitude_error_db_LR=(20 * np.log10(np.asarray(v['amplitude_LR']) / amp)).tolist()) for v in check]
            max_error = {key: max(abs(v[key + '_frequency_error_hz']) for v in errors) for key in ['moving', 'fixed']}
            amp_error = float(np.median(abs(np.array([v['amplitude_error_db_LR'] for v in errors]))))
            item.update(status='compared', training_moving_frequency_hz=moving, training_fixed_frequency_hz=fixed,
                        training_amplitude_LR=amp.tolist(), check=errors, maximum_frequency_error_hz=max_error,
                        median_absolute_amplitude_error_db=amp_error,
                        diagnostic_targets_met={key: value <= 4 and amp_error <= 3 for key, value in max_error.items()})
        out.append(item)
    return out
