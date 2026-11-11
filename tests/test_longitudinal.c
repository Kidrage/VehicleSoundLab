#include "drive/drive.h"
#include "drive/powertrain.h"
#include "drive/longitudinal.h"
#include "drive/shift.h"
#include "core/engine.h"
#include "profiles/vehicle.h"
#include <math.h>
#include <stdio.h>
static int failures;
#define CHECK(x,m) do { if(!(x)) { fprintf(stderr,"FAIL: %s\n",m);++failures; } } while(0)
static void running(VslDrive *d,int gear,double speed,double pedal) {
    vsl_drive_reset(d,0);d->lifecycle=VSL_RUNNING;d->gear=gear;
    d->speed_kph=speed;d->rpm=fmax(850,speed*vsl_gear_ratio(gear));
    d->throttle=d->engine_throttle=pedal;
    d->clutch_capacity_nm=900;
}
static double coast(double dt) {
    VslDrive d;int i;running(&d,0,180,0);
    for(i=0;i<(int)(10/dt+.5);++i)vsl_longitudinal_step(&d,850,8500,dt);
    return d.speed_kph;
}
int main(void) {
    const VslVehicleProfile *v=vsl_vehicle_profile(0);
    VslDrive d,a;VslParams p=vsl_default_params(0);
    double torque,force,ratio,omega,speed,low,high,before;
    int gear,i;
    CHECK(fabs(vsl_available_torque(0,6500,8500)-600)<1e-8,"600 Nm brochure torque anchor");
    torque=vsl_available_torque(0,8000,8500);
    CHECK(fabs(torque*8000*2*VSL_PI/60-470000)<1,"470 kW brochure power anchor");
    for(i=1;i<=8500;++i)CHECK(vsl_available_torque(0,i,8500)*i*2*VSL_PI/60<=470001,"interpolation cannot exceed the sourced peak-power envelope");
    for(gear=1;gear<=7;++gear) {
        speed=35;ratio=vsl_angular_per_metre(gear);omega=speed*3.6*vsl_gear_ratio(gear)*2*VSL_PI/60;
        force=vsl_wheel_force(0,400,ratio,1);
        CHECK(fabs(force*speed-400*omega*v->efficiency)<1e-7,"SI ratio gives loss-only forward power transfer");
        force=vsl_wheel_force(0,-50,ratio,1);
        CHECK(fabs(force*speed-(-50)*omega/v->efficiency)<1e-7,"backdrive includes transmission loss in correct direction");
        CHECK(vsl_wheel_force(0,400,ratio,0)==0,"open clutch transmits no shaft torque");
    }
    running(&d,3,90,.8);vsl_longitudinal_step(&d,850,8500,.005);low=d.vehicle.acceleration_mps2;
    running(&d,4,90,.8);vsl_longitudinal_step(&d,850,8500,.005);high=d.vehicle.acceleration_mps2;
    CHECK(low>high && high>0,"equal pedal/speed accelerates more in the lower usable gear");
    CHECK(d.vehicle.effective_mass_kg==v->mass_kg+v->wheel_equivalent_kg&&d.vehicle.solver_active,
        "engine inertia is solved separately and is not counted again in vehicle mass");
    running(&d,0,120,1);d.blip=1;vsl_longitudinal_step(&d,850,8500,.005);
    CHECK(d.vehicle.wheel_force_n==0 && d.vehicle.acceleration_mps2<0,"neutral pedal/blip cannot provide road thrust");
    running(&d,4,120,0);d.clutch_transfer=0;d.blip=1;vsl_longitudinal_step(&d,850,8500,.005);
    CHECK(d.vehicle.wheel_force_n==0,"open-clutch rev match has no engine braking or thrust");
    running(&d,3,100,0);a=d;a.gear=4;a.rpm=100*vsl_gear_ratio(4);
    vsl_longitudinal_step(&d,850,8500,.005);vsl_longitudinal_step(&a,850,8500,.005);
    CHECK(d.vehicle.engine_brake_n>a.vehicle.engine_brake_n && a.vehicle.engine_brake_n>0,"closed throttle braking scales with gearing and shaft speed");
    running(&d,3,90,.8);before=d.speed_kph;
    CHECK(vsl_shift_request(&d,4,8500),"upshift accepted");
    vsl_shift_step(&d,850,8500,.005);vsl_longitudinal_step(&d,850,8500,.005);
    CHECK(d.vehicle.transmitted_gear==3 && d.vehicle.sample_clutch>0,"disconnect retains the original driven gear");
    CHECK(d.speed_kph>before,"disconnect torque decays rather than using the target ratio immediately");
    running(&d,4,160,0);d.brake=1;
    for(i=0;i<3000;++i) {
        before=d.speed_kph;vsl_longitudinal_step(&d,850,8500,.005);
        CHECK(d.speed_kph<=before && d.speed_kph>=0,"unpowered braking is passive and cannot reverse");
        CHECK(d.vehicle.service_brake_n-d.vehicle.wheel_force_n<=v->traction_mu*v->mass_kg*9.80665+1e-7,"combined tyre braking is grip bounded");
    }
    CHECK(d.speed_kph==0 && d.vehicle.acceleration_mps2==0,"brake holds the rest boundary without negative-speed chatter");
    CHECK(fabs(coast(.005)-coast(.0025))<.002,"coast integration converges when the time step is halved");
    p.drive_mode=VSL_PEDALS;p.auto_gear=0;p.gear=3;p.throttle=1;
    running(&d,3,120,1);d.last_start=p.start_id;
    for(i=0;i<20000;++i)vsl_drive_step(&d,&p,.005);
    CHECK(isfinite(d.speed_kph) && d.rpm<=8500 && d.speed_kph<8500/vsl_gear_ratio(3)*1.03,"fixed gear stabilizes below overspeed without a global speed cap");
    p.ignition=0;p.brake=1;d.speed_kph=100;
    for(i=0;i<1500;++i) {
        before=d.speed_kph;vsl_drive_step(&d,&p,.005);
        CHECK(d.speed_kph<=before && d.vehicle.wheel_force_n==0,"shutdown disconnects engine and keeps service braking available");
    }
    CHECK(d.speed_kph==0 && d.lifecycle==VSL_OFF,"brakes stop a rolling ignition-off vehicle");
    if(!failures)puts("PASS: SI power transfer, gear force, inertial proxy, passive braking, shift ratio, limiter and convergence");
    return failures?1:0;
}
