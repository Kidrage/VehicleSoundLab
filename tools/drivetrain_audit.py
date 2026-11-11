"""Read emitted driving telemetry; distinguish sample and full-run energy sums."""
import csv
from pathlib import Path
import math


def read_trace(path):
    return list(csv.DictReader(Path(path).open(encoding='utf-8')))


def metrics(rows):
    return dict(max_speed_kph=max(float(r['speed_kph']) for r in rows),
        last_speed_kph=float(rows[-1]['speed_kph']),last_rpm=float(rows[-1]['rpm']),
        shift_events=int(rows[-1]['shifts']),overrun_events=int(rows[-1]['overruns']),
        aborted_shifts=int(rows[-1]['aborted_shifts']),states=sorted(set(r['operating'] for r in rows)))


def energy_audit(rows):
    last=rows[-1];number=lambda key:float(last[key])
    sums={key:number('total_'+key) for key in ['kinetic_delta_j','engine_work_j','road_work_j',
        'clutch_heat_j','transmission_loss_j','numerical_loss_j']}
    balance=sums['kinetic_delta_j']-sums['engine_work_j']+sum(sums[k] for k in
        ['road_work_j','clutch_heat_j','transmission_loss_j','numerical_loss_j'])
    assert int(last['energy_steps'])>100 and number('max_energy_error_j')<1e-6
    assert abs(balance)<.0005,('cumulative energy closure',balance)
    for row in rows:
        if row['coupling_active']!='1':continue
        for key in ['energy_error_j','kinetic_after_j','clutch_torque_nm','clutch_slip_rad_s']:
            assert math.isfinite(float(row[key])),key
        assert abs(float(row['energy_error_j']))<1e-6
        for key in ['clutch_heat_j','transmission_loss_j','numerical_loss_j']:assert float(row[key])>=-1e-7
        assert float(row['clutch_torque_nm'])*float(row['clutch_slip_rad_s'])>=-1e-6
        omega=float(row['rpm'])*2*math.pi/60;speed=float(row['speed_kph'])/3.6
        # Display RPM/kph are rounded to 0.001; do not give their reconstructed
        # kinetic energy the full-precision solver's tolerance.
        display_energy=.5*.22*omega*omega+.5*1670*speed*speed
        assert abs(display_energy-float(row['kinetic_after_j']))<30
        if float(row['force_sample_clutch'])==0 or row['force_gear']=='0':assert float(row['wheel_force_n'])==0
    return dict(scope='All RUNNING integration steps accumulated by C; start/catch/stop kinematics and bench excluded.',
        steps=int(last['energy_steps']),max_step_energy_error_j=number('max_energy_error_j'),
        cumulative_balance_error_j=balance,**sums)
