#include "core/engine.h"
#include "core/modules.h"
#include "drive/fueling.h"
#include "drive/drive.h"
#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
static int failures;
#define CHECK(x,m) do { if(!(x)) { fprintf(stderr,"FAIL: %s\n",m);++failures; } } while(0)
static void step(VslDrive *d,VslParams *p,double seconds) {
    int i;for(i=0;i<(int)(seconds*200+.5);++i)vsl_fueling_step(d,p,.005);
}
static void coast(VslDrive *d) {
    memset(d,0,sizeof *d);d->profile=VSL_V10;d->lifecycle=VSL_RUNNING;
    d->rpm=5000;d->gear=3;d->load=-.3;
}
static void run(VslEngine *e,VslParams *p,double seconds,double *energy) {
    float output[480],stems[240*VSL_OBJECTS];int i,c,blocks=(int)(seconds*200+.5);
    vsl_set_params(e,p);
    if(energy)memset(energy,0,sizeof(double)*VSL_OBJECTS);
    for(i=0;i<blocks;++i) {
        int j;vsl_process_layout(e,output,240,2,stems);
        if(energy)for(j=0;j<240;++j)for(c=0;c<VSL_OBJECTS;++c)
            energy[c]+=stems[j*VSL_OBJECTS+c]*stems[j*VSL_OBJECTS+c];
        for(j=0;j<480;++j)CHECK(isfinite(output[j]),"fuel transitions and the cavity remain finite");
    }
}
int main(void) {
    VslDrive d;VslParams p=vsl_default_params(VSL_V10);
    VslEngine *a=malloc(sizeof *a),*b=malloc(sizeof *b);
    double cut[VSL_OBJECTS],legacy[VSL_OBJECTS],dry[VSL_OBJECTS];int i;
    if(!a||!b) { free(a);free(b);return 2; }
    coast(&d);step(&d,&p,.13);CHECK(d.fuel.mode==VSL_FUEL_DELAY&&d.fuel.command==1,"brief closed throttle preserves fuel before qualification");
    d.engine_throttle=.02;step(&d,&p,.005);CHECK(d.fuel.closed_seconds==0,"a nonclosed throttle resets the entry timer");
    d.engine_throttle=0;step(&d,&p,.14);CHECK(d.fuel.mode==VSL_FUEL_CUT&&d.fuel.command==0,"qualified high-RPM overrun cuts combustion supply");
    d.rpm=1600;step(&d,&p,.2);CHECK(d.fuel.mode==VSL_FUEL_CUT,"RPM hysteresis holds an existing cut above the resume threshold");
    d.rpm=1290;step(&d,&p,.005);CHECK(d.fuel.mode==VSL_FUEL_RESUME&&d.fuel.command==1,"fuel returns before the idle region");
    coast(&d);d.gear=0;step(&d,&p,.15);CHECK(d.fuel.command==1,"neutral lift uses a longer qualification interval");
    step(&d,&p,.07);CHECK(d.fuel.mode==VSL_FUEL_CUT,"neutral high-RPM closed lift can qualify");
    d.blip=.001;step(&d,&p,.005);CHECK(d.fuel.command==1&&d.fuel.mode==VSL_FUEL_RESUME,"even a small internal rev-match blip restores supply immediately");
    d.blip=0;step(&d,&p,.05);CHECK(d.fuel.command==1,"resume hold prevents immediate cut chatter");
    coast(&d);step(&d,&p,.2);d.engine_throttle=.04;step(&d,&p,.005);
    CHECK(d.fuel.command==1,"driver reopening restores fuel independently of brake or gear");
    coast(&d);step(&d,&p,.2);p.fuel_cut=0;step(&d,&p,.005);CHECK(d.fuel.command==1,"user bypass releases an active cut");
    p.fuel_cut=1;p.profile=VSL_SCIFI;coast(&d);step(&d,&p,1);CHECK(d.fuel.command==1,"creative SCI-FI profile keeps continuous excitation");
    p.profile=VSL_V10;coast(&d);d.load=.1;step(&d,&p,1);CHECK(d.fuel.mode==VSL_FUEL_FIRE,"positive load cannot qualify as overrun even with a closed synthetic pedal");
    d.lifecycle=VSL_OFF;step(&d,&p,.005);CHECK(d.fuel.mode==VSL_FUEL_OFF&&d.fuel.command==0,"shutdown clears supply and timers");
    /* Actual sound: compare identical crank/control histories with cut enabled
       and bypassed; pumping/rotational sound must survive the removed fire. */
    p=vsl_default_params(0);p.rpm=5000;p.load=.85;p.space=0;p.backfire=0;
    vsl_init(a,48000,48271);vsl_init(b,48000,48271);
    a->smooth.space=b->smooth.space=0;
    run(a,&p,2,NULL);p.fuel_cut=0;run(b,&p,2,NULL);
    p.load=-.4;p.fuel_cut=1;run(a,&p,1,NULL);run(a,&p,.25,cut);
    p.fuel_cut=0;run(b,&p,1,NULL);run(b,&p,.25,legacy);
    printf("Measured isolated exhaust energies: motored %.9g, fired %.9g, ratio %.6f\n",cut[VSL_EXHAUST_L],legacy[VSL_EXHAUST_L],cut[VSL_EXHAUST_L]/legacy[VSL_EXHAUST_L]);
    CHECK(a->drive.rpm==b->drive.rpm&&a->control.phase==b->control.phase,"cut never stops or retimes the crank");
    CHECK(a->excitation.firing<1e-12,"actual sample-rate firing excitation settles to zero");
    CHECK(cut[VSL_EXHAUST_L]>1e-6&&cut[VSL_EXHAUST_L]<legacy[VSL_EXHAUST_L]*.1,"motored pressure survives at lower energy than fired exhaust");
    CHECK(cut[VSL_BODY]==legacy[VSL_BODY]&&cut[VSL_AIR_L]==legacy[VSL_AIR_L],"body and air do not inherit the fuel gate");
    CHECK(cut[VSL_MECHANICAL]>1e-6,"driven mechanical sound remains active during fuel cut");
    CHECK(a->mechanical.rotating_seed==b->mechanical.rotating_seed,"fired strikes cannot change the independent rotational variation sequence");
    { unsigned fired=a->mechanical.fired_strikes,rotating=a->mechanical.rotating_strikes;
      p.fuel_cut=1;run(a,&p,.1,NULL);
      CHECK(a->mechanical.fired_strikes==fired&&a->mechanical.rotating_strikes>rotating,"settled fuel cut removes fired impacts while crank-driven impacts continue"); }
    {
        VslParams off=p;*b=*a;off.fuel_cut=1;off.ignition=0;
        run(b,&off,.2,NULL);
        CHECK(b->excitation.firing<1e-12,"ignition off during a cut cannot reintroduce fired pressure into the shutdown tail");
    }
    p.fuel_cut=1;p.pumping=0;run(a,&p,1,NULL);run(a,&p,.25,dry);
    CHECK(dry[VSL_EXHAUST_L]<1e-12,"motored pressure knob independently removes the new source");
    p.load=.8;run(a,&p,.2,NULL);CHECK(a->excitation.firing>.99999,"reopening restores actual fired audio promptly");
    for(i=0;i<3;++i) {
        double rates[]={16000,48000,192000};
        vsl_init(a,rates[i],48271);a->drive.lifecycle=VSL_RUNNING;a->drive.fuel.command=0;
        a->control.rpm=10000;a->voice.combustion=1;
        { int j;double energy=0;for(j=0;j<(int)rates[i];++j) {
            VslObjectFrame o={0};vsl_clocks_tick(a);vsl_excitation_tick(a,&o);
            CHECK(isfinite(o.sample[0])&&fabs(o.sample[0])<1,"motored cavity stable across supported sample rates");energy+=o.sample[0]*o.sample[0];
          } CHECK(energy>1e-5,"stability check exercises a nonzero pressure source"); }
    }
    free(a);free(b);
    if(!failures)puts("PASS: fueling hysteresis/dwell, blip/refuel, creative bypass, active motored pressure and rotational sound independence");
    return failures?1:0;
}
