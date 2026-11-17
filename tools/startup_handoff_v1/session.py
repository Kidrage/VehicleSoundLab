"""Bounded neutral startup captures; no second vehicle model or audio processing."""
from copy import deepcopy
import json

from event_designer.package import write_json
from vehicle_controller import recipe, take
from vehicle_scenarios.capture import capture, replay

RATE = 48000
START_SECONDS = .35
DURATION_SECONDS = 8.


def generate(bridge, source_preset, output, crank_seconds=None, catch_level=None):
    """Explicitly reauthor controls/parameters from the older candidate document.

    The old document's schema and engine identity are not migrated or accepted.
    Current recipe/take constructors bind the actual current C engine instead.
    """
    control = deepcopy(source_preset['control'])
    control.update(mode=1, ignition=0, start_id=0, throttle=0., brake=.65,
                   automatic=0, gear=0, backfire=0)
    control['input'].update(source=0, valid=0, sequence=0, speed_mps=0.,
                            acceleration_mps2=0., tire_slip=0.)
    control['events'].update(enabled=1, manual_sequence=0)
    control['events']['levels'] = [0., 1., 1., 0., 0., 0., 0.]
    if catch_level is not None:
        control['events']['levels'][2] = catch_level
    response = deepcopy(source_preset['startup_response'])
    if crank_seconds is not None:
        response['crank_seconds'] = crank_seconds
    overrides = deepcopy(source_preset['event_overrides'])
    selection = source_preset['catalog']
    value = take.create(bridge, selection, control, overrides, response)
    started = deepcopy(control)
    started.update(ignition=1, start_id=1)
    take.append(value, round(START_SECONDS * RATE), started)
    value['frames'] = round(DURATION_SECONDS * RATE)
    output.mkdir(parents=True, exist_ok=False)
    result, rows, transitions = capture(bridge, value, output)
    replayed = replay(bridge, value)
    checks = dict(
        replay_pcm_exact=result['pcm_sha256'] == replayed['pcm_sha256'],
        replay_notices_exact=value['source_events'] == replayed['source_events'],
        replay_state_exact=result['final_state'] == replayed['final_state'],
        dry_stems_reconstruct=result['native_reconstruction_error'] < 2e-6,
        ends_running_idle=result['final_state']['lifecycle'] == 4
                          and result['final_state']['operating'] == 0,
        remains_stationary=result['final_state']['speed_mps'] == 0.,
        legacy_startup_disabled=all(row['rms_legacy_event'] == 0.
                                   and row['rms_startup'] == 0.
                                   and row['rms_catch'] == 0. for row in rows),
    )
    result.update(checks=checks, replay=replayed, result='passed' if all(checks.values()) else 'failed',
                  bridge_sha256=bridge.sha256, voices_sha256=bridge.voices_sha256,
                  timbre_accepted=False, physical_rpm_measured=False,
                  description='Composite engineering demo: A exterior continuous DNA, F2 idle, A mixed-cabin startup events. Not a matched-view recording reconstruction.')
    write_json(output/'verification.json', result)
    document = recipe.create(bridge, selection, control, '踏板驾驶', overrides, response)
    recipe.validate(bridge, document)
    write_json(output/'startup.recipe.json', document)
    assert all(checks.values()), json.dumps(checks)
    return result
