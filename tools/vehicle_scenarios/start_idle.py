"""A pedal-controlled lifecycle with room to hear both parked idle intervals."""
from copy import deepcopy

from vehicle_controller import take
from .scenario import RATE


def start_idle_lifecycle(bridge, selection, control, overrides, response, event_policy=None, dna_bank=None):
    control = deepcopy(control)
    control.update(mode=1, ignition=0, start_id=0, gear=0, automatic=0,
                   throttle=0., brake=.65)
    control['input'].update(source=0, valid=0, sequence=0, speed_mps=0.,
                            acceleration_mps2=0., tire_slip=0.)
    control['events']['manual_sequence'] = 0
    value = take.create(bridge, selection, control, overrides, response, event_policy, dna_bank)
    instructions = [
        (0., 'OFF', {}, 'Stopped in neutral; no automatic playback.'),
        (.35, 'START', dict(ignition=1, start_id=1), 'Explicit start edge.'),
        (6., 'LAUNCH', dict(automatic=1, gear=1, throttle=.20, brake=0.), 'Select drive and release brake.'),
        (7., 'ACCELERATE', dict(throttle=.92), 'Sport automatic acceleration.'),
        (19., 'LIFT', dict(throttle=0.), 'Hold gear on lift; afterfire requires an eligible reference.'),
        (21., 'BRAKE', dict(brake=.85), 'Brake with safe automatic downshifts.'),
        (30., 'PARKED_IDLE', dict(brake=.65), 'Hold the stopped drive gear; hear the returning idle layer without requesting another shift.'),
        (34., 'IGNITION_OFF', dict(ignition=0), 'Stop and release source/event tails.'),
        (36., 'END', {}, 'End after shutdown.'),
    ]
    stages = []
    for seconds, name, changes, note in instructions:
        control.update(changes)
        frame = round(seconds*RATE)
        if 0 < seconds < 36:
            take.append(value, frame, control)
        stages.append(dict(frame=frame, seconds=seconds, name=name,
                           control=deepcopy(control), note=note))
    value['frames'] = 36*RATE
    return value, dict(schema='vsl.vehicle-scenario/1', name='start_idle_lifecycle',
        sample_rate=RATE, stages=stages, trajectory='All RPM/speed/load/states are produced by the C driver.',
        timbre_accepted=False, goal_complete=False)
