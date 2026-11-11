#include "core/engine.h"
#include "core/modules.h"
#include "drive/fueling.h"
#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
static int failures;
#define CHECK(x,m) do { if(!(x)) { fprintf(stderr,"FAIL: %s\n",m);++failures; } } while(0)
static void truth_table(VslEngine *e) {
    const double rates[]={16000,48000,192000};int r,life,combustion,fuel,i;
    for(r=0;r<3;++r)for(life=VSL_OFF;life<=VSL_STOPPING;++life)
    for(combustion=0;combustion<2;++combustion)for(fuel=0;fuel<2;++fuel) {
        int expected=(life==VSL_RUNNING||life==VSL_CATCH)&&combustion&&fuel;
        int rotating=life!=VSL_OFF&&life!=VSL_READY;
        vsl_init(e,rates[r],48271);e->drive.lifecycle=(VslLifecycle)life;
        e->drive.combustion=combustion?.5:0;e->drive.fuel.command=fuel;
        e->control.rpm=2400;e->voice.mechanical_gain=e->voice.mechanical_motion_gain=.08;
        e->excitation.firing=1; /* deliberately stale, positive audio envelope */
        CHECK(vsl_fueling_allows_firing(&e->drive)==expected,"event permission needs lifecycle, combustion and supply together");
        for(i=0;i<(int)(rates[r]*.05);++i) {
            vsl_clocks_tick(e);(void)vsl_mechanical_modal_tick(e);
        }
        CHECK(expected?e->mechanical.fired_strikes>=9:e->mechanical.fired_strikes==0,
            "stale amplitude cannot create a forbidden firing, permitted firings remain active");
        CHECK(rotating?e->mechanical.rotating_strikes>=19:e->mechanical.rotating_strikes==0,
            "rotational impacts follow crank lifecycle independently of fuel");
    }
}
static void real_transitions(VslEngine *e,int stop) {
    VslParams p=vsl_default_params(VSL_V10);float out[480];int block,observed=0;
    unsigned invalid=0,rotation=0;double energy=0;
    vsl_init(e,48000,48271);p.rpm=5000;p.load=.85;p.backfire=0;p.space=0;
    for(block=0;block<800;++block) {
        unsigned fired=e->mechanical.fired_strikes,rotating=e->mechanical.rotating_strikes;
        float stems[240*VSL_OBJECTS];int allowed,i;
        if(stop&&block>=400)p.ignition=0;
        if(!stop)p.load=block>=400&&block<600?-.4:.85;
        vsl_set_params(e,&p);CHECK(vsl_process_layout(e,out,240,2,stems),"actual sound transition rendered");
        allowed=(e->drive.lifecycle==VSL_RUNNING||e->drive.lifecycle==VSL_CATCH)&&
            e->drive.combustion>0&&e->drive.fuel.command>0;
        if(block>=400&&!allowed) {
            ++observed;invalid+=e->mechanical.fired_strikes-fired;
            rotation+=e->mechanical.rotating_strikes-rotating;
            for(i=0;i<240;++i)energy+=stems[i*VSL_OBJECTS+VSL_MECHANICAL]*stems[i*VSL_OBJECTS+VSL_MECHANICAL];
        }
    }
    CHECK(observed>30&&invalid==0,"first and later denied control periods create no fired strikes");
    CHECK(rotation>30&&energy>1e-8,"rotation and nonzero structural response survive fire denial");
    if(!stop)CHECK(e->drive.fuel.command==1&&e->mechanical.fired_strikes>500,"refuel restores fired scheduling");
}
static void independent_rotation(VslEngine *a,VslEngine *b) {
    unsigned i;double before,after;
    vsl_init(a,48000,48271);a->drive.lifecycle=VSL_RUNNING;
    a->drive.combustion=a->drive.fuel.command=1;a->control.rpm=2400;
    a->voice.mechanical_gain=a->voice.mechanical_motion_gain=.08;*b=*a;
    b->drive.fuel.command=0;
    for(i=0;i<4800;++i) {
        vsl_clocks_tick(a);vsl_clocks_tick(b);
        (void)vsl_mechanical_modal_tick(a);(void)vsl_mechanical_modal_tick(b);
    }
    CHECK(a->mechanical.fired_strikes>0&&b->mechanical.fired_strikes==0,"different permission exercises separate fired scheduling");
    CHECK(a->mechanical.rotating_strikes==b->mechanical.rotating_strikes&&
        a->mechanical.rotating_seed==b->mechanical.rotating_seed,"fire denial cannot consume or alter rotating RNG/events");
    before=b->mechanical.stored_energy;b->control.rpm=0;b->drive.lifecycle=VSL_OFF;
    (void)vsl_mechanical_modal_tick(b);after=b->mechanical.stored_energy;
    CHECK(before>1e-10&&after>0&&after<before,"denial preserves existing resonator ringdown");
    for(i=0;i<24000;++i)(void)vsl_mechanical_modal_tick(b);
    CHECK(b->mechanical.stored_energy<after*1e-18,"zero-RPM stored response decays to silence");
}
int main(void) {
    VslEngine *a=malloc(sizeof *a),*b=malloc(sizeof *b);
    if(!a||!b) { free(a);free(b);return 2; }
    truth_table(a);real_transitions(a,0);real_transitions(a,1);independent_rotation(a,b);
    free(a);free(b);if(!failures)puts("PASS: event permission matrix, real shutdown/cut/refuel, rotating RNG independence and ringdown");
    return failures?1:0;
}
