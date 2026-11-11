#include "drive/drive.h"
#include "core/engine.h"
#include <math.h>
#include <stdio.h>
static int failures;
#define CHECK(x,m) do { if(!(x)) { fprintf(stderr,"FAIL: %s\n",m);++failures; } } while(0)

static void continuous_start(int profile,double dt) {
    VslParams p=vsl_default_params(profile);VslDrive d;
    double step_peak=0,peak=0,entry=-1,old_flare=0;int i,caught=0,rose=0,fell=0;
    p.drive_mode=VSL_PEDALS;p.throttle=0;p.gear=0;p.auto_gear=0;
    vsl_drive_reset(&d,profile);
    for(i=0;i<(int)(2/dt);++i) {
        double previous=d.rpm;VslLifecycle before=d.lifecycle;
        vsl_drive_step(&d,&p,dt);
        CHECK(isfinite(d.rpm) && d.rpm>=0 && d.combustion>=0 && d.combustion<=1,"finite lifecycle rotation and permission");
        if(d.lifecycle==VSL_CRANK)CHECK(d.combustion==0 && d.fuel.command==0,"starter rotation is not fired pressure");
        if(d.lifecycle==VSL_CATCH) {
            step_peak=fmax(step_peak,fabs(d.rpm-previous));peak=fmax(peak,d.rpm);
            if(before!=VSL_CATCH) { caught=1;entry=d.rpm;CHECK(fabs(d.rpm-previous)<1e-9,"catch entry retains actual starter speed"); }
            if(d.lifecycle_flare>old_flare+1e-9)rose=1;
            if(d.lifecycle_flare<old_flare-1e-9)fell=1;
        }
        CHECK(d.lifecycle_flare>=0 && d.lifecycle_flare<=1,"bounded independent start flare");
        if(d.lifecycle==VSL_RUNNING && before==VSL_CATCH)
            CHECK(fabs(d.rpm-previous)<3,"idle handover has no RPM step");
        old_flare=d.lifecycle_flare;
        CHECK(d.speed_kph==0 && d.overrun_events==0,"stationary start has no propulsion or lift pops");
    }
    CHECK(caught && entry>200 && entry<225,"catch enters at starter speed, not 1150 RPM");
    CHECK(peak>1100 && peak<=1150.000001 && rose && fell,"causal start flare rises and settles");
    CHECK(step_peak/dt<8000,"finite bounded catch acceleration instead of one-tick RPM jump");
    CHECK(d.lifecycle==VSL_RUNNING && fabs(d.rpm-vsl_profile(profile)->idle_rpm)<1 && d.start_events==1,"settles once to selected profile idle");
}

int main(void) {
    VslDrive d;VslParams p;int profile,i,stage;
    for(profile=0;profile<VSL_PROFILE_COUNT;++profile) {
        continuous_start(profile,.001);continuous_start(profile,.005);continuous_start(profile,.01);
    }
    for(stage=0;stage<2;++stage) {
        p=vsl_default_params(0);p.drive_mode=VSL_PEDALS;vsl_drive_reset(&d,0);
        for(i=0;i<(stage?75:20);++i)vsl_drive_step(&d,&p,.005);
        CHECK(d.lifecycle==(stage?VSL_CATCH:VSL_CRANK),"cancellation covers starter and firing rise");
        p.ignition=0;
        for(i=0;i<180;++i) {
            vsl_drive_step(&d,&p,.005);
            CHECK(d.combustion==0 && d.fuel.command==0 && d.lifecycle_flare==0,"cancel immediately removes firing permission/flare");
        }
        CHECK(d.lifecycle==VSL_OFF && d.start_events==1 && d.overrun_events==0,"cancelled start stops without pop/retrigger");
        p.ignition=1;vsl_drive_step(&d,&p,.005);
        CHECK(d.lifecycle==VSL_READY,"ignition alone cannot replay last start edge");
        ++p.start_id;
        for(i=0;i<300;++i)vsl_drive_step(&d,&p,.005);
        CHECK(d.lifecycle==VSL_RUNNING && d.start_events==2,"fresh start after cancellation works");
    }
    /* Changing engine selection with a previously consumed start token must
       not manufacture a new button edge after the drive struct is reset. */
    p=vsl_default_params(0);p.ignition=0;vsl_drive_reset(&d,0);
    vsl_drive_step(&d,&p,.005);p.profile=1;p.ignition=1;
    vsl_drive_step(&d,&p,.005);
    CHECK(d.lifecycle==VSL_READY && d.start_events==0,"off profile switch preserves consumed start token");
    if(!failures)puts("PASS: continuous start, causal flare, all template idles, cancellation, fresh edges");
    return failures?1:0;
}
