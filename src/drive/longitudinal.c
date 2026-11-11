#include "longitudinal.h"
#include "powertrain.h"
#include "coupling.h"
#include "clutch.h"
#include "profiles/vehicle.h"
#include "core/modules.h"
#include <math.h>
#include <string.h>
#define GRAVITY 9.80665
void vsl_longitudinal_step(VslDrive *d,double idle,double maxrpm,double dt) {
    const VslVehicleProfile *p=vsl_vehicle_profile(d->profile);
    VslVehicle *v=&d->vehicle;
    double speed=fmax(0,d->speed_kph/3.6),ratio;
    VslCouplingInput input={0};VslCouplingResult result;VslClutchControl control;
    int running=d->lifecycle==VSL_RUNNING;
    memset(v,0,sizeof *v);
    v->transmitted_gear=running?vsl_transmitted_gear(d):0;
    v->sample_speed_mps=speed;v->sample_rpm=d->rpm;
    v->sample_clutch=running?vsl_clamp(d->clutch_transfer,0,1):0;
    /* Downshift blips stay open-clutch. Upshift synchronization uses friction
       under closed engine throttle, with its energy exchange accounted for. */
    v->sample_pedal=running?d->throttle*vsl_clamp(d->shift_gain,0,1):0;
    v->available_torque_nm=vsl_available_torque(d->profile,d->rpm,maxrpm);
    ratio=vsl_angular_per_metre(v->transmitted_gear);
    v->rolling_n=p->rolling_coefficient*p->mass_kg*GRAVITY;
    v->aerodynamic_n=.5*p->air_density_kg_m3*p->drag_area_m2*speed*speed;
    v->service_brake_n=p->brake_g*p->mass_kg*GRAVITY*pow(vsl_clamp(d->brake,0,1),p->brake_exponent);
    v->service_brake_n=fmin(v->service_brake_n,p->traction_mu*p->mass_kg*GRAVITY);
    v->effective_mass_kg=p->mass_kg+p->wheel_equivalent_kg;
    vsl_clutch_control(d,idle,maxrpm,v->rolling_n+v->aerodynamic_n+v->service_brake_n,v->service_brake_n,dt,&control);
    input.omega_rad_s=d->rpm*(2*VSL_PI/60);input.speed_mps=speed;
    input.engine_torque_nm=control.torque_nm;input.road_force_n=v->rolling_n+v->aerodynamic_n+v->service_brake_n;
    input.engine_inertia_kg_m2=p->engine_inertia_kg_m2;input.mass_kg=v->effective_mass_kg;
    input.angular_per_metre=ratio;input.efficiency=p->efficiency;
    input.positive_capacity_nm=control.positive_capacity_nm;input.negative_capacity_nm=control.negative_capacity_nm;input.dt=dt;
    if(!vsl_coupling_solve(&input,&result))return;
    v->solver_active=running;v->shaft_torque_nm=control.torque_nm;
    v->requested_torque_nm=control.requested_torque_nm;v->idle_torque_nm=control.idle_torque_nm;
    v->governor_reduction_nm=control.governor_reduction_nm;v->clutch_capacity_nm=d->clutch_capacity_nm;
    v->clutch_torque_nm=result.clutch_torque_nm;v->clutch_slip_rad_s=result.slip_rad_s;v->clutch_locked=result.locked;
    v->wheel_force_n=vsl_wheel_force(d->profile,result.clutch_torque_nm,ratio,1);
    v->engine_brake_n=fmax(0,-v->wheel_force_n);
    v->engine_work_j=result.engine_work_j;v->road_work_j=result.road_work_j;
    v->clutch_heat_j=result.clutch_heat_j;v->transmission_loss_j=result.transmission_loss_j;
    v->numerical_loss_j=result.numerical_loss_j;v->energy_before_j=result.energy_before_j;
    v->energy_after_j=result.energy_after_j;v->energy_error_j=result.energy_error_j;
    if(running) {
        VslCouplingAudit *audit=&d->coupling_audit;
        ++audit->steps;audit->kinetic_delta_j+=result.energy_after_j-result.energy_before_j;
        audit->engine_work_j+=result.engine_work_j;audit->road_work_j+=result.road_work_j;
        audit->clutch_heat_j+=result.clutch_heat_j;audit->transmission_loss_j+=result.transmission_loss_j;
        audit->numerical_loss_j+=result.numerical_loss_j;
        audit->max_energy_error_j=fmax(audit->max_energy_error_j,fabs(result.energy_error_j));
    }
    if(running) { d->rpm=result.omega_rad_s/(2*VSL_PI/60);d->engine_throttle=control.engine_pedal; }
    v->acceleration_mps2=(result.speed_mps-speed)/dt;
    d->speed_kph=result.speed_mps*3.6;
    /* Acoustic control becomes a bounded acceleration in g. */
    d->acceleration=vsl_clamp(v->acceleration_mps2/GRAVITY,-1,1);
}
