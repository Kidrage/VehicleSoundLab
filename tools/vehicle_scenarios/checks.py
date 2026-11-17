"""Explicit full-lifecycle assertions; acoustic acceptance remains separate."""
import numpy as np


def inspect(bridge, value, report, rows, replay):
    results = []

    def check(name, ok, evidence):
        results.append(dict(name=name, passed=bool(ok), evidence=evidence))

    life = sorted(set(row['lifecycle'] for row in rows))
    operating = sorted(set(row['operating'] for row in rows))
    check('full_lifecycle_states', all(k in life for k in (0, 2, 3, 4, 5)), life)
    check('driving_operating_states', all(k in operating for k in (0, 2, 4, 5, 6, 7)), operating)
    check('native_reconstruction', report['native_reconstruction_error'] < 2e-6,
          report['native_reconstruction_error'])
    check('finite_and_bounded_rpm', all(np.isfinite(row['rpm']) and 0 <= row['rpm'] <= 10000 for row in rows),
          [min(row['rpm'] for row in rows), max(row['rpm'] for row in rows)])
    check('monitor_headroom', report['monitor_peak'] < 1., report['monitor_peak'])
    idle = [row for row in rows if 28. <= row['seconds'] < 29.3]
    check('stopped_idle', idle and all(row['speed_mps'] < .02 and row['operating'] == 0 and row['idle_weight'] > .95 for row in idle),
          dict(max_speed_mps=max((r['speed_mps'] for r in idle), default=-1),
               min_idle_weight=min((r['idle_weight'] for r in idle), default=-1)))
    lift = [row for row in rows if 15.9 <= row['seconds'] < 17.9]
    check('sport_lift_holds_gear', lift and len(set(row['gear'] for row in lift)) == 1 and len(set(row['shifts'] for row in lift)) == 1,
          dict(gears=sorted(set(row['gear'] for row in lift)), shifts=sorted(set(row['shifts'] for row in lift))))
    off = [row for row in rows if row['seconds'] >= 31.]
    check('off_tail_is_silent', off and all(row['lifecycle'] == 0 and row['rms'] < 1e-6 for row in off),
          max((row['rms'] for row in off), default=-1))
    final = report['final_state']
    check('automatic_shifts_and_overrun', final['shifts'] >= 2 and final['overruns'] >= 1,
          dict(shifts=final['shifts'], overruns=final['overruns']))
    check('bounded_event_pool_and_log', final['event_peak'] <= 4 and
          final['event_overflow'] == final['event_log_lost'] == final['event_rejected'] == 0,
          {key:final[key] for key in ('event_peak', 'event_overflow', 'event_log_lost', 'event_rejected')})
    starts = [e for e in value['source_events'] if e['action'] == 1]
    check('one_crank_and_one_catch', [e['type'] for e in starts].count(1) == [e['type'] for e in starts].count(2) == 1, starts)
    live = {}
    identities = set()
    valid = True
    for e in value['source_events']:
        key = e['slot']
        if e['action'] == 1:
            valid &= key not in live and e['id'] not in identities and e['frame'] >= e['requested_frame']
            live[key] = e['id']
            identities.add(e['id'])
        elif e['action'] == 2:
            valid &= live.pop(key, None) == e['id']
        else:
            valid = False
    check('event_lifetimes_and_slot_identity', valid and not live, value['source_events'])
    check('variable_block_replay_pcm_exact', report['pcm_sha256'] == replay['pcm_sha256'],
          dict(direct=report['pcm_sha256'], replay=replay['pcm_sha256'], pattern=replay['block_pattern']))
    check('variable_block_replay_notices_exact', value['source_events'] == replay['source_events'],
          dict(direct=value['source_events'], replay=replay['source_events']))
    check('variable_block_replay_state_exact', report['final_state'] == replay['final_state'],
          dict(direct=report['final_state'], replay=replay['final_state']))
    return results
