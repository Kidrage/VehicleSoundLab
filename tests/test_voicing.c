#include "core/engine.h"
#include "core/modules.h"
#include <math.h>
#include <stdio.h>
#include <stdlib.h>
static int failures;
#define CHECK(x,m) do { if(!(x)) { fprintf(stderr,"FAIL: %s\n",m);++failures; } } while(0)
static void advance(VslEngine *e,double seconds) {
    int i;for(i=0;i<(int)(seconds*200+.5);++i)vsl_orchestrate(e,.005);
}
static void loaded(VslEngine *e) {
    vsl_init(e,48000,48271);e->target.drive_mode=VSL_PEDALS;
    e->drive.lifecycle=VSL_RUNNING;e->drive.operating=VSL_PULL;
    e->drive.rpm=5000;e->drive.load=.8;e->drive.throttle=e->drive.engine_throttle=.85;
    e->drive.combustion=1;e->drive.shift_gain=1;advance(e,2);
}
int main(void) {
    VslEngine *e=malloc(sizeof *e),*b=malloc(sizeof *b);VslVoicing before;int i;
    double sum=0;
    if(!e||!b) { free(e);free(b);return 2; }
    loaded(e);before=e->voice;
    e->drive.operating=VSL_SHIFT_CUT;e->drive.shift_gain=.35;advance(e,.13);
    CHECK(e->voice.body_gain/before.body_gain>e->voice.dna_gain/before.dna_gain+.15,
        "shift keeps body energy while exhaust torque is cut");
    CHECK(e->voice.mechanical_gain/before.mechanical_gain>e->voice.intake_gain/before.intake_gain+.30,
        "mechanical tail and intake have independent cut responses");
    CHECK(e->voice.high_gain/before.high_gain<.4,"high detail has a decisive shift cut");
    e->drive.shift_gain=1;e->drive.operating=VSL_SHIFT_RECOVER;advance(e,1);
    CHECK(e->voice.dna_gain>.7*before.dna_gain && e->voice.intake_gain>.7*before.intake_gain,
        "cut layers recover instead of remaining latched off");
    loaded(e);before=e->voice;e->drive.operating=VSL_OVERRUN;
    e->drive.load=-.4;e->drive.throttle=e->drive.engine_throttle=0;advance(e,.1);
    CHECK(e->voice.body_gain/before.body_gain>e->voice.intake_gain/before.intake_gain+.4,
        "lift keeps body mass after the intake closes");
    CHECK(e->voice.high_gain/before.high_gain<.25,"overrun closes sustained high-frequency excitation");
    loaded(e);loaded(b);b->drive.operating=VSL_CRUISE;advance(b,2);
    CHECK(b->voice.intake_gain<e->voice.intake_gain*.8 && b->voice.cutoff_ratio<e->voice.cutoff_ratio,
        "matched RPM/load states change colour and intake, not only a display label");
    loaded(e);loaded(b);e->drive.acceleration=.7;advance(e,1);advance(b,1);
    CHECK(e->voice.intake_gain>b->voice.intake_gain*1.05,"longitudinal acceleration colours intake");
    e->target.drive_mode=VSL_BENCH;advance(e,1);
    CHECK(e->voice.accel<1e-6,"bench does not inherit longitudinal colour from pedal mode");
    e->drive.load=-.4;e->drive.acceleration=-.7;e->target.drive_mode=VSL_PEDALS;advance(e,1);
    CHECK(e->voice.decel>.6,"negative acceleration reaches exhaust control");
    loaded(e);loaded(b);
    e->drive.operating=b->drive.operating=VSL_SHIFT_CUT;
    e->drive.shift_gain=b->drive.shift_gain=.35;
    e->drive.load=b->drive.load=.3;e->drive.engine_throttle=b->drive.engine_throttle=.5;
    e->drive.operating=VSL_REV_MATCH;e->drive.blip=.5;advance(e,.08);advance(b,.08);
    CHECK(e->voice.intake_gain>b->voice.intake_gain*1.4 && e->voice.high_gain>b->voice.high_gain*1.4,
        "rev match briefly restores intake and upper exhaust while clutch torque is cut");
    e->drive.lifecycle=VSL_OFF;e->drive.combustion=0;advance(e,4);
    CHECK(e->voice.dna_gain<1e-12 && e->voice.high_gain<1e-12 && e->voice.body_gain<1e-12,
        "all combustion layers settle silent after shutdown");
    for(i=0;i<VSL_OPERATING_COUNT;++i)sum+=e->voice.state_mix[i];
    CHECK(fabs(sum-1)<1e-12,"state mixture remains normalized after settling");
    free(e);free(b);
    if(!failures)puts("PASS: per-layer cut/recovery, release mass, state colour, motion and shutdown");
    return failures?1:0;
}
