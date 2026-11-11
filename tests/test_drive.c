#include "drive/drive.h"
#include "drive/powertrain.h"
#include "core/engine.h"
#include "profiles/vehicle.h"
#include <math.h>
#include <stdio.h>
static int failures;
#define CHECK(x,m) do { if(!(x)) { fprintf(stderr,"FAIL: %s\n",m);++failures; } } while(0)
static void advance(VslDrive *d,VslParams *p,double seconds) { int i;for(i=0;i<(int)(seconds*200+.5);++i)vsl_drive_step(d,p,.005); }
int main(void) {
    VslDrive d,a;VslParams p=vsl_default_params(0);unsigned events,coast_shifts=0;int i;
    p.drive_mode=VSL_PEDALS;p.ignition=0;p.start_id=0;p.throttle=1;
    vsl_drive_reset(&d,0);advance(&d,&p,1);
    CHECK(d.lifecycle==VSL_OFF && d.speed_kph==0 && d.combustion==0,"pedal cannot power an unstarted engine");
    p.ignition=1;advance(&d,&p,1);
    CHECK(d.lifecycle==VSL_READY && d.combustion==0 && d.rpm==0,"ignition is not start");
    ++p.start_id;advance(&d,&p,.15);
    CHECK(d.lifecycle==VSL_CRANK && d.combustion==0,"crank is distinct from combustion");
    advance(&d,&p,.3);CHECK(d.lifecycle==VSL_CATCH,"catch is a distinct transition");
    advance(&d,&p,1);CHECK(d.lifecycle==VSL_RUNNING && d.start_events==1,"successful start latch");
    advance(&d,&p,2);CHECK(d.start_events==1,"repeated parameters do not restart engine");
    p.ignition=0;advance(&d,&p,.1);CHECK(d.lifecycle==VSL_STOPPING && d.combustion==0,"shutdown stops combustion");
    advance(&d,&p,.7);CHECK(d.lifecycle==VSL_OFF,"shutdown reaches OFF");
    p=vsl_default_params(0);p.drive_mode=VSL_AUTODRIVE;
    vsl_drive_reset(&d,0);vsl_drive_reset(&a,0);
    for(i=0;i<6000;++i) {
        unsigned previous_shifts=d.shift_events;
        vsl_drive_step(&d,&p,.005);vsl_drive_step(&a,&p,.005);
        if(d.running_seconds>=14 && d.running_seconds<17)coast_shifts+=d.shift_events-previous_shifts;
        CHECK(d.rpm>=0 && d.rpm<=9000 && d.speed_kph>=0 && isfinite(d.rpm),"bounded driving state");
        CHECK(d.rpm==a.rpm && d.speed_kph==a.speed_kph,"deterministic simulation clock");
        if(d.vehicle.solver_active) {
            const VslVehicleProfile *v=vsl_vehicle_profile(0);
            double omega=d.rpm*(2*VSL_PI/60),speed=d.speed_kph/3.6;
            double kinetic=.5*v->engine_inertia_kg_m2*omega*omega+.5*(v->mass_kg+v->wheel_equivalent_kg)*speed*speed;
            CHECK(fabs(kinetic-d.vehicle.energy_after_j)<1e-6,"driving/shift code cannot overwrite the mechanically solved RPM or vehicle state");
            if(d.blip>0)CHECK(d.vehicle.clutch_torque_nm==0,"internal matching throttle remains isolated by the open clutch");
        }
    }
    CHECK(d.shift_events>=3,"pedals produce integrated automatic shifts");
    CHECK(d.overrun_events>=1,"armed high RPM release triggers overrun");
    CHECK(coast_shifts==0,"sport auto holds its gear throughout the lift-only window");
    CHECK(d.speed_kph<2,"service brake brings vehicle to rest");
    CHECK(d.aborted_shifts==0,"integrated sport scenario completes without failed clutch matches");
    {
        const VslCouplingAudit *e=&d.coupling_audit;
        double balance=e->kinetic_delta_j-e->engine_work_j+e->road_work_j+e->clutch_heat_j+e->transmission_loss_j+e->numerical_loss_j;
        CHECK(e->steps>5000&&e->max_energy_error_j<1e-6&&fabs(balance)<1e-4,"all running control steps close the cumulative energy budget, not just sparse trace rows");
        CHECK(e->clutch_heat_j>0&&e->transmission_loss_j>0&&e->numerical_loss_j>0,"launch/shift heat, driveline loss and numerical damping remain explicit");
    }
    p=vsl_default_params(0);p.drive_mode=VSL_PEDALS;p.auto_gear=1;p.brake=1;
    vsl_drive_reset(&d,0);d.lifecycle=VSL_RUNNING;d.last_start=p.start_id;
    d.gear=5;d.speed_kph=150;d.rpm=5145;advance(&d,&p,.2);
    CHECK(d.gear==4 && d.shift_events==1,"sport braking requests a safe downshift");
    vsl_drive_reset(&d,0);d.lifecycle=VSL_RUNNING;d.last_start=p.start_id;
    d.gear=3;d.speed_kph=140;d.rpm=7770;advance(&d,&p,.2);
    CHECK(d.gear==3 && d.shift_events==0,"braking cannot downshift into excessive engine speed");
    {
        double low,high;
        d.lifecycle=VSL_RUNNING;d.shift_gain=1;d.speed_kph=100;d.throttle=0;
        d.gear=3;d.rpm=100*vsl_gear_ratio(3);low=vsl_engine_braking(&d,8500);
        d.gear=4;d.rpm=100*vsl_gear_ratio(4);high=vsl_engine_braking(&d,8500);
        CHECK(low>high && high>0,"lower coupled gear produces more engine braking at equal road speed");
        d.gear=0;CHECK(vsl_engine_braking(&d,8500)==0,"neutral transmits no engine braking");
        d.gear=3;d.throttle=.4;CHECK(vsl_engine_braking(&d,8500)==0,"open throttle does not receive closed-throttle drag");
    }
    p=vsl_default_params(0);p.drive_mode=VSL_BENCH;p.rpm=5000;p.load=.8;
    vsl_drive_reset(&d,0);advance(&d,&p,2);p.load=0;advance(&d,&p,.3);
    CHECK(d.overrun_events==1,"fast release produces one qualified event");
    events=d.overrun_events;advance(&d,&p,2);CHECK(d.overrun_events==events,"closed pedal cannot retrigger continuously");
    p.load=.8;advance(&d,&p,1);
    for(i=0;i<200;++i) { p.load=.8*(1-i/199.);vsl_drive_step(&d,&p,.005); }
    advance(&d,&p,.3);CHECK(d.overrun_events==events,"slow release does not pop");
    p.rpm=900;p.load=.8;advance(&d,&p,2);p.load=0;advance(&d,&p,.4);
    CHECK(d.overrun_events==events,"low RPM release does not pop");
    p.load=-.6;advance(&d,&p,.5);CHECK(d.load<0,"signed bench load survives control chain");
    p=vsl_default_params(0);p.drive_mode=VSL_BENCH;p.rpm=5000;p.load=.12;
    vsl_drive_reset(&d,0);
    for(i=0;i<600;++i) {
        vsl_drive_step(&d,&p,.005);
        CHECK(d.operating!=VSL_OVERRUN,"positive bench load cannot briefly select overrun during startup");
    }
    p.load=-.4;advance(&d,&p,.1);CHECK(d.operating==VSL_OVERRUN,"negative bench load selects overrun");
    p=vsl_default_params(0);p.drive_mode=VSL_PEDALS;p.auto_gear=0;p.gear=0;p.throttle=1;
    vsl_drive_reset(&d,0);advance(&d,&p,3);
    CHECK(d.gear==0 && d.rpm>7000 && d.speed_kph==0,"neutral free rev does not propel vehicle");
    p=vsl_default_params(0);p.drive_mode=VSL_PEDALS;p.brake=1;
    vsl_drive_reset(&d,0);advance(&d,&p,5);
    CHECK(d.overrun_events==0,"braking alone cannot arm pops");
    if(!failures)puts("PASS: lifecycle, latch, pedals, coupling, gears, lift gates, signed load and neutral");
    return failures?1:0;
}
