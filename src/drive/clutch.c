#include "clutch.h"
#include "powertrain.h"
#include "profiles/clutch.h"
#include "profiles/vehicle.h"
#include "profiles/transmission.h"
#include "core/modules.h"
#include <math.h>
#include <string.h>
#define RAD_PER_RPM (2*VSL_PI/60)
static double ease(double x) { x=vsl_clamp(x,0,1);return x*x*(3-2*x); }
void vsl_clutch_control(VslDrive *d,double idle,double maxrpm,double road,double service,
    double dt,VslClutchControl *c) {
    const VslClutchProfile *p=vsl_clutch_profile(d->profile);
    const VslVehicleProfile *v=vsl_vehicle_profile(d->profile);
    const VslTransmissionProfile *t=vsl_transmission_profile(d->profile);
    double ratio=vsl_angular_per_metre(vsl_transmitted_gear(d));
    double loss=vsl_engine_loss(d->profile,d->rpm,maxrpm),available=vsl_available_torque(d->profile,d->rpm,maxrpm);
    double desired,launch=idle+d->throttle*(p->launch_rpm-idle),wheel=d->speed_kph/3.6*ratio;
    double omega=d->rpm*RAD_PER_RPM,grip=v->traction_mu*v->mass_kg*9.80665;
    memset(c,0,sizeof *c);d->blip=0;
    if(d->lifecycle!=VSL_RUNNING) { d->clutch_capacity_nm=0;return; }
    c->engine_pedal=d->throttle*d->shift_gain;
    c->idle_torque_nm=vsl_clamp(loss+p->idle_gain_nm_per_rpm*(idle-d->rpm),0,p->idle_max_nm)*
        ease((idle+p->idle_window_rpm-d->rpm)/p->idle_window_rpm)*(1-ease(d->throttle/.10));
    c->requested_torque_nm=vsl_shaft_torque(d->profile,d->rpm,idle,maxrpm,c->engine_pedal)+c->idle_torque_nm;
    if(d->shifting&&d->shift_stage==VSL_SHIFT_MATCH&&d->gear) {
        double target=fmax(idle,d->shift_target_rpm-(d->shift_direction<0?p->match_undershoot_rpm:0));
        double alpha=vsl_clamp((target-d->rpm)/t->match_response+d->shift_target_rate,-t->max_fall,t->max_rise)*RAD_PER_RPM;
        double wanted=v->engine_inertia_kg_m2*alpha;
        c->idle_torque_nm=0;
        c->engine_pedal=vsl_clamp((wanted+loss)/(available+loss),0,d->shift_direction<0?t->blip_max:1);
        if(d->shift_direction>0)c->engine_pedal=0;
        c->requested_torque_nm=vsl_shaft_torque(d->profile,d->rpm,idle,maxrpm,c->engine_pedal);
        if(d->shift_direction<0&&c->engine_pedal>0) { d->blip=c->engine_pedal;d->operating=VSL_REV_MATCH; }
    }
    c->torque_nm=c->requested_torque_nm;
    desired=p->capacity_nm*vsl_clamp(d->clutch_transfer,0,1);
    if(!ratio)desired=0;
    /* Releasing an already-open clutch must not first increase capacity. */
    if(d->shifting&&d->shift_stage==VSL_SHIFT_DISCONNECT)desired=fmin(desired,d->clutch_capacity_nm);
    if(!d->shifting&&ratio&&wheel<(launch+100)*RAD_PER_RPM) {
        desired=vsl_clamp(c->requested_torque_nm+p->launch_gain_nm_per_rad_s*(omega-launch*RAD_PER_RPM),0,desired);
        desired*=ease(d->throttle/.10);
    }
    if(desired<=0)d->clutch_capacity_nm=0;
    else d->clutch_capacity_nm=fmin(desired,d->clutch_capacity_nm+(desired-d->clutch_capacity_nm)*(1-exp(-dt/p->capacity_tau)));
    if(ratio) {
        c->positive_capacity_nm=fmin(d->clutch_capacity_nm,grip/(ratio*v->efficiency));
        c->negative_capacity_nm=fmin(d->clutch_capacity_nm,fmax(0,grip-service)*v->efficiency/ratio);
        if(!d->shifting||d->shift_stage==VSL_SHIFT_ENGAGE) {
            double target=d->shifting?d->shift_target_rpm*RAD_PER_RPM:fmax(launch*RAD_PER_RPM,wheel);
            double alpha=(target-omega)*p->governor_per_s;
            if(d->shifting)alpha+=d->shift_target_rate*RAD_PER_RPM;
            else if(wheel>=launch*RAD_PER_RPM)
                alpha+=ratio*(c->positive_capacity_nm*ratio*v->efficiency-road)/(v->mass_kg+v->wheel_equivalent_kg);
            /* Engine-side launch/traction governor; every torque reduction is
               explicit. Do not create unaccounted angular acceleration by
               changing engine RPM or reflecting a second copy of its inertia. */
            c->torque_nm=fmin(c->requested_torque_nm,fmax(-loss,c->positive_capacity_nm+v->engine_inertia_kg_m2*alpha));
        }
    }
    c->governor_reduction_nm=c->requested_torque_nm-c->torque_nm;
    c->engine_pedal=vsl_clamp((c->torque_nm+loss)/(available+loss),0,1);
}
