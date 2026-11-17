#include "drive/drive.h"
#include "core/engine.h"
#include <stdio.h>

static int failures;
#define CHECK(x,m) do { if(!(x)) { fprintf(stderr,"FAIL: %s\n",m);++failures; } } while(0)

static VslParams controls(void) {
    VslParams p=vsl_default_params(0);
    p.drive_mode=VSL_PEDALS;p.auto_gear=0;p.gear=0;
    p.ignition=0;p.start_id=0;p.throttle=0;p.brake=.65;
    return p;
}

int main(void) {
    VslDrive d;VslParams p;int i,seen_running=0;
    p=controls();vsl_drive_reset(&d,0);
    vsl_drive_step(&d,&p,.005);
    CHECK(d.lifecycle==VSL_OFF&&d.gear==0,"stopped OFF adopts the manual selector before startup");
    p.ignition=1;vsl_drive_step(&d,&p,.005);
    CHECK(d.lifecycle==VSL_READY&&d.gear==0,"READY keeps the selected neutral");
    p.start_id=1;
    for(i=0;i<600;++i) {
        vsl_drive_step(&d,&p,.005);
        CHECK(d.gear==0&&!d.shifting&&d.shift_events==0,"neutral startup never invents a gear change");
        if(d.lifecycle==VSL_RUNNING) {
            seen_running=1;
            CHECK(d.operating==VSL_IDLE,"catch enters idle without SHIFT_CUT or SHIFT_RECOVER");
        }
    }
    CHECK(seen_running&&d.speed_kph==0,"neutral startup reaches stationary running idle");

    p=controls();p.ignition=1;p.start_id=1;vsl_drive_reset(&d,0);
    vsl_drive_step(&d,&p,.005);
    CHECK(d.lifecycle==VSL_CRANK&&d.gear==0&&d.shift_events==0,"start edge in the first frame uses the preselected gear");

    p=controls();vsl_drive_reset(&d,0);p.ignition=1;p.gear=2;
    vsl_drive_step(&d,&p,.005);
    CHECK(d.lifecycle==VSL_READY&&d.gear==2&&d.requested_gear==2,"stopped manual selector applies in READY without a shift");
    p.gear=0;vsl_drive_step(&d,&p,.005);
    CHECK(d.gear==0&&d.shift_events==0,"READY selector changes do not create running shift events");

    p=controls();vsl_drive_reset(&d,0);p.auto_gear=1;
    vsl_drive_step(&d,&p,.005);
    CHECK(d.gear==1,"automatic policy retains its existing initial gear");
    p=controls();vsl_drive_reset(&d,0);p.drive_mode=VSL_BENCH;
    vsl_drive_step(&d,&p,.005);
    CHECK(d.gear==1,"RPM bench is unaffected by the manual selector initialization");

    p=controls();vsl_drive_reset(&d,0);
    { VslKinematics input={10.,0.,0.};vsl_drive_step_kinematic(&d,&p,.005,&input); }
    CHECK(d.gear==1&&d.speed_kph==36.,"moving external input never uses stopped preselection");

    p=controls();p.ignition=1;p.start_id=1;vsl_drive_reset(&d,0);
    d.lifecycle=VSL_RUNNING;d.last_start=1;d.rpm=850;d.gear=1;
    vsl_drive_step(&d,&p,.005);
    CHECK(d.shift_events==1&&d.shifting&&d.operating==VSL_SHIFT_CUT,"real neutral selection while running still uses the transmission");
    if(!failures)puts("PASS: stopped manual preselection, neutral startup, moving/auto/bench guards and real running shifts");
    return failures?1:0;
}
