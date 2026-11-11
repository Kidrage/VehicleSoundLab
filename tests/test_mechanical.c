#include "core/engine.h"
#include "core/modules.h"
#include "core/modal.h"
#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
static int failures;
#define CHECK(x,m) do { if(!(x)) { fprintf(stderr,"FAIL: %s\n",m);++failures; } } while(0)
static void analytic_modes(void) {
    double rates[]={16000,44100,48000,96000,192000};int r,i;
    for(r=0;r<5;++r) {
        VslMode m;double sr=rates[r],fraction=.37/sr,max_error=0,energy_before;
        vsl_mode_init(&m,2240,.009,sr);
        for(i=0;i<100;++i)CHECK(vsl_mode_tick(&m)==0,"unexcited modal filter cannot create energy");
        vsl_mode_strike(&m,.17,fraction);
        energy_before=m.real*m.real+m.imag*m.imag;
        for(i=1;i<=(int)(sr*.08);++i) {
            double t=i/sr+fraction,expected=.17*exp(-t/.009)*sin(2*VSL_PI*2240*t);
            max_error=fmax(max_error,fabs(vsl_mode_tick(&m)-expected));
        }
        CHECK(max_error<1e-12,"fractional strike, mode frequency and decay follow analytic response at all rates");
        CHECK(fabs((m.real*m.real+m.imag*m.imag)/energy_before-exp(-2*(int)(sr*.08)/(sr*.009)))<1e-14,"stored energy decays with the specified time constant");
        vsl_mode_init(&m,sr*.45,.01,sr);vsl_mode_strike(&m,1,0);
        CHECK(vsl_mode_tick(&m)==0,"out-of-band mode is disabled");
    }
}
static double mechanical(VslEngine *e) {
    VslObjectFrame o={0};vsl_clocks_tick(e);vsl_mechanical_tick(e,&o);return o.sample[VSL_MECHANICAL];
}
static void struck_structure(VslEngine *e) {
    int i;double peak=0,initial,tail=0;
    vsl_init(e,48000,48271);e->drive.lifecycle=VSL_RUNNING;e->control.rpm=1200;
    e->drive.combustion=e->drive.fuel.command=1;
    e->voice.mechanical_motion_gain=e->voice.mechanical_gain=.08;e->excitation.firing=1;
    (void)vsl_mechanical_modal_tick(e);
    for(i=0;i<48000;++i)peak=fmax(peak,fabs(mechanical(e)));
    CHECK(e->mechanical.fired_strikes>=99&&e->mechanical.fired_strikes<=100,"one pressure strike per firing event per 720-degree cycle");
    CHECK(e->mechanical.rotating_strikes>=199&&e->mechanical.rotating_strikes<=200,"two rotational strike events per cylinder cycle");
    CHECK(peak>1e-5&&peak<.1,"structural output is active and bounded");
    { unsigned fired=e->mechanical.fired_strikes,rotating=e->mechanical.rotating_strikes;
      e->excitation.firing=0;
      for(i=0;i<4800;++i)(void)mechanical(e);
      CHECK(e->mechanical.fired_strikes==fired&&e->mechanical.rotating_strikes>rotating,"zero firing pressure cannot stop rotational impacts"); }
    initial=e->mechanical.stored_energy;e->control.rpm=0;e->drive.lifecycle=VSL_OFF;
    for(i=0;i<24000;++i) { double s=mechanical(e);if(i<480)tail+=s*s; }
    CHECK(initial>1e-10&&tail>1e-10,"stopping the crank leaves an audible finite ringing tail");
    CHECK(e->mechanical.stored_energy<initial*1e-18,"ringdown continues at zero RPM and reaches silence");
    e->target.mechanical_model=0;for(i=0;i<48000;++i)(void)mechanical(e);
    CHECK(e->mechanical.mix==0,"model bypass reaches exact legacy branch");
    e->target.mechanical_model=1;(void)mechanical(e);
    CHECK(e->mechanical.mix>0&&e->mechanical.mix<.002,"live model changes use a finite crossfade");
    e->smooth.profile=VSL_SCIFI;e->control.rpm=5000;
    for(i=0;i<4800;++i)CHECK(mechanical(e)==0,"SCI-FI receives no structural excitation");
}
static void motion_envelope(VslEngine *e) {
    int i;vsl_init(e,48000,48271);e->drive.lifecycle=VSL_CRANK;e->drive.rpm=300;
    for(i=0;i<100;++i)vsl_orchestrate(e,.005);
    CHECK(e->voice.mechanical_motion_gain>0&&e->voice.mechanical_gain==0,"starter rotation excites structure before combustion permission");
    e->drive.lifecycle=VSL_OFF;e->drive.rpm=0;
    for(i=0;i<200;++i)vsl_orchestrate(e,.005);
    CHECK(e->voice.mechanical_motion_gain<1e-15,"mechanical motion envelope releases after stop");
}
int main(void) {
    VslEngine *e=malloc(sizeof *e);if(!e)return 2;
    analytic_modes();struck_structure(e);motion_envelope(e);free(e);
    if(!failures)puts("PASS: analytic modal decay/fractional timing, crank/fired strikes, zero-RPM tail, startup motion and model switching");
    return failures?1:0;
}
