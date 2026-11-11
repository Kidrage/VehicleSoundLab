#include "powertrain.h"
#include "core/modules.h"
#include "core/engine.h"
#include "profiles/vehicle.h"
#include <math.h>
static double ease(double x) { x=vsl_clamp(x,0,1);return x*x*(3-2*x); }
double vsl_gear_ratio(int gear) {
    return gear>=1&&gear<=7?vsl_vehicle_profile(0)->gear_rpm_per_kph[gear-1]:0;
}
double vsl_angular_per_metre(int gear) { return vsl_gear_ratio(gear)*3.6*(2*VSL_PI/60); }
int vsl_transmitted_gear(const VslDrive *d) {
    return d->shifting&&d->shift_stage==VSL_SHIFT_DISCONNECT?d->previous_gear:d->gear;
}
double vsl_available_torque(int profile,double rpm,double maxrpm) {
    return vsl_vehicle_profile(profile)->peak_torque_nm*vsl_torque_fraction(maxrpm>0?rpm/maxrpm:0);
}
double vsl_shaft_torque(int profile,double rpm,double idle,double maxrpm,double pedal) {
    const VslVehicleProfile *p=vsl_vehicle_profile(profile);
    double x=maxrpm>0?vsl_clamp(rpm/maxrpm,0,1):0;
    double loss=vsl_engine_loss(profile,rpm,maxrpm);
    double limiter=1-ease((x-p->limiter_start)/(1-p->limiter_start));
    (void)idle;
    return vsl_clamp(pedal,0,1)*limiter*(vsl_available_torque(profile,rpm,maxrpm)+loss)-loss;
}
double vsl_engine_loss(int profile,double rpm,double maxrpm) {
    const VslVehicleProfile *p=vsl_vehicle_profile(profile);
    double x=maxrpm>0?vsl_clamp(rpm/maxrpm,0,1):0;
    return (p->loss_low_nm+p->loss_high_nm*x*x)*vsl_clamp(rpm/100,0,1);
}
double vsl_wheel_force(int profile,double torque,double ratio,double clutch) {
    double efficiency=vsl_vehicle_profile(profile)->efficiency;
    /* Positive shaft power loses energy toward the wheels. On backdrive,
       the wheels supply the engine loss AND transmission loss. */
    return torque*ratio*vsl_clamp(clutch,0,1)*(torque>=0?efficiency:1/efficiency);
}
/* Compatibility diagnostic in kph/s, not another force applied to the car. */
double vsl_engine_braking(const VslDrive *d,double max_rpm) {
    const VslVehicleProfile *p=vsl_vehicle_profile(d->profile);
    double idle=vsl_profile(d->profile)->idle_rpm,ratio,locked,torque,mass;
    if(d->lifecycle!=VSL_RUNNING || max_rpm<=0)return 0;
    ratio=vsl_angular_per_metre(vsl_transmitted_gear(d));
    locked=vsl_clamp((d->speed_kph*vsl_gear_ratio(vsl_transmitted_gear(d))-idle)/600,0,1);
    torque=vsl_shaft_torque(d->profile,d->rpm,idle,max_rpm,d->throttle*d->shift_gain);
    mass=p->mass_kg+p->wheel_equivalent_kg+p->engine_inertia_kg_m2*ratio*ratio*locked*d->clutch_transfer;
    return fmax(0,-vsl_wheel_force(d->profile,torque,ratio,d->clutch_transfer))*locked/mass*3.6;
}
