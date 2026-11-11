#include "drive/drive.h"
#include "core/engine.h"
#include "drive/shift.h"
#include "drive/powertrain.h"
#include <math.h>
#include <stdio.h>
static int failures;
#define CHECK(x,m) do { if(!(x)) { fprintf(stderr,"FAIL: %s\n",m);++failures; } } while(0)
static void running(VslDrive *d,VslParams *p,int gear,double speed) {
    *p=vsl_default_params(0);p->drive_mode=VSL_PEDALS;p->auto_gear=0;p->gear=gear;
    vsl_drive_reset(d,0);d->lifecycle=VSL_RUNNING;d->last_start=p->start_id;
    d->gear=gear;d->speed_kph=speed;d->rpm=fmax(850,speed*vsl_gear_ratio(gear));
}
int main(void) {
    VslDrive d,b;VslParams p,q;int i,blips=0,engages=0,up_sync=0;double rise=0;
    running(&d,&p,4,110);p.gear=3;p.brake=.45;
    for(i=0;i<180;++i) {
        double speed=d.speed_kph,rpm=d.rpm;VslShiftStage stage=d.shift_stage;
        vsl_drive_step(&d,&p,.005);
        CHECK(d.throttle==0,"braking rev match leaves driver pedal closed");
        CHECK(d.speed_kph<=speed,"internal blip never accelerates the car under braking");
        if(d.blip>0) {
            ++blips;rise+=d.rpm-rpm;
            CHECK(d.shift_stage==VSL_SHIFT_MATCH && d.clutch_transfer==0,"blip occurs only with the clutch disconnected");
            CHECK(d.engine_throttle>0 && d.operating==VSL_REV_MATCH,"internal throttle reaches the sound state");
        }
        if(d.shift_stage==VSL_SHIFT_ENGAGE && stage!=VSL_SHIFT_ENGAGE) {
            ++engages;CHECK(fabs(d.shift_error)<=80,"engagement starts only after RPM match");
        }
        if(d.shifting)CHECK(d.rpm-rpm<=28000*.005+.0001,"rev rise has a bounded actuator rate");
    }
    CHECK(blips>2 && rise>600 && engages==1 && !d.shifting && d.gear==3,"closed-pedal 4 to 3 completes a controlled rev match");
    CHECK(d.overrun_events==0 && !d.overrun_armed,"internal blip cannot arm driver-release pops");
    running(&d,&p,3,110);p.throttle=.8;d.throttle=d.engine_throttle=.8;
    b=d;q=p;p.gear=4;
    for(i=0;i<60;++i) {
        vsl_drive_step(&d,&p,.005);vsl_drive_step(&b,&q,.005);
        CHECK(d.blip==0,"upshift never requests a downshift blip");
        if(d.shift_stage==VSL_SHIFT_MATCH&&d.vehicle.clutch_torque_nm>0) {
            ++up_sync;CHECK(d.engine_throttle==0&&d.vehicle.clutch_heat_j>=0,
                "upshift synchronization uses passive clutch friction under closed engine throttle");
        }
    }
    CHECK(d.rpm<b.rpm && d.speed_kph<b.speed_kph-.8,"upshift lowers RPM and actually reduces wheel thrust");
    CHECK(up_sync>2,"upshift transmits stored engine energy instead of waiting only for free engine drag");
    running(&d,&p,3,140);p.gear=2;
    for(i=0;i<10;++i)vsl_drive_step(&d,&p,.005);
    CHECK(d.gear==3 && d.shift_events==0,"unsafe downshift is rejected before disconnect");
    running(&d,&p,4,110);p.gear=3;
    for(i=0;i<30 && d.blip==0;++i)vsl_drive_step(&d,&p,.005);
    CHECK(d.blip>0,"shutdown test reaches a live rev match");
    p.ignition=0;vsl_drive_step(&d,&p,.005);
    CHECK(!d.shifting && d.blip==0 && d.engine_throttle==0 && d.shift_stage==VSL_SHIFT_NONE,"ignition off clears blip and all pending clutch stages");
    running(&d,&p,3,110);p.gear=0;
    for(i=0;i<160;++i) { vsl_drive_step(&d,&p,.005);CHECK(d.blip==0,"neutral entry has no automatic blip"); }
    CHECK(d.gear==0 && !d.shifting,"neutral entry completes");p.gear=4;
    for(i=0;i<180;++i) { vsl_drive_step(&d,&p,.005);CHECK(d.blip==0,"neutral exit has no automatic downshift blip"); }
    CHECK(d.gear==4 && !d.shifting && !d.aborted_shifts,"safe neutral engagement matches before coupling");
    running(&d,&p,4,110);p.gear=3;vsl_drive_step(&d,&p,.005);
    d.speed_kph=200;vsl_drive_step(&d,&p,.005);
    CHECK(d.gear==0 && d.aborted_shifts==1 && !d.shifting,"target overspeed during a shift aborts into neutral");
    if(!failures)puts("PASS: bounded rev matching, clutch torque, pedal/event separation, overspeed, neutral and shutdown");
    return failures?1:0;
}
