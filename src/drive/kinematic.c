#include "kinematic.h"
#include "powertrain.h"
#include "core/modules.h"
#include <math.h>
#include <string.h>
void vsl_kinematic_adopt(VslDrive *d,const VslKinematics *p) {
    d->speed_kph=p->speed_mps*3.6;
    d->acceleration=vsl_clamp(p->acceleration_mps2/9.80665,-1,1);
}
void vsl_kinematic_step(VslDrive *d,const VslKinematics *p,double idle,double maxrpm,double dt) {
    VslVehicle *v=&d->vehicle;double target,load;
    vsl_kinematic_adopt(d,p);memset(v,0,sizeof *v);
    v->sample_speed_mps=p->speed_mps;v->sample_rpm=d->rpm;
    v->acceleration_mps2=p->acceleration_mps2;
    v->available_torque_nm=vsl_available_torque(d->profile,d->rpm,maxrpm);
    if(d->lifecycle!=VSL_RUNNING)return;
    if(!d->gear)target=idle+d->throttle*(maxrpm-idle);
    else {
        double coupled=d->speed_kph*vsl_gear_ratio(d->gear)*(1+.2*p->tire_slip);
        double launch=idle+d->throttle*(2600-idle);
        double blend=vsl_clamp((d->speed_kph-4)/20,0,1);blend=blend*blend*(3-2*blend);
        target=launch*(1-blend)+fmax(idle,coupled)*blend;
    }
    if(d->shifting)target=d->shift_stage==VSL_SHIFT_DISCONNECT?d->shift_from_rpm:d->shift_target_rpm;
    target=vsl_clamp(target,idle,maxrpm);
    d->rpm+=(target-d->rpm)*(1-exp(-dt/(d->shifting?.055:.11)));
    d->blip=d->shifting&&d->shift_direction<0&&d->shift_target_rpm>d->rpm?.4:0;
    d->engine_throttle=vsl_clamp(d->throttle*d->shift_gain+d->blip,0,1);
    load=d->engine_throttle-.16*(1-d->throttle)*vsl_clamp(p->speed_mps/10,0,1);
    v->sample_pedal=d->engine_throttle;v->sample_clutch=d->clutch_transfer;
    v->transmitted_gear=vsl_transmitted_gear(d);v->shaft_torque_nm=load*v->available_torque_nm;
    /* No coupling solver, wheel integration or energy-audit advance here. */
}
