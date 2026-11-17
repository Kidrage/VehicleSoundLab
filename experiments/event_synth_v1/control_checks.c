#include "event_control/api.h"
#include <math.h>
#include <stdio.h>
#define CHECK(x) do{if(!(x)){fprintf(stderr,"event control line%d: %s\n",__LINE__,#x);return 3;}}while(0)
static int check_stopping(void) {
    EcState s;EcControl c=ec_default();EcObservation o={0};EcCommand cmd;
    unsigned releases=0,stops=0;
    c.enabled=1;ec_init(&s,127);CHECK(ec_set(&s,&c,0));
    o.lifecycle=EC_CRANK;ec_observe(&s,&o,0);
    CHECK(ec_poll(&s,0,&cmd)&&cmd.type==ES_ENGAGE);
    /* Abort before the delayed crank starts. Its queued start must disappear. */
    o.lifecycle=EC_STOPPING;ec_observe(&s,&o,240);
    while(ec_poll(&s,48000,&cmd)) {
        if(cmd.operation==EC_START){CHECK(cmd.type==ES_STOP);++stops;}
        else {CHECK(cmd.type!=ES_STOP&&cmd.release_seconds>0&&cmd.release_seconds<=.02);++releases;}
    }
    CHECK(stops==1&&releases==7&&!s.overflow);
    ec_observe(&s,&o,480);CHECK(!ec_poll(&s,48000,&cmd));
    /* Running-engine shift/overrun commands may already be queued for later. */
    ec_init(&s,127);CHECK(ec_set(&s,&c,0));
    o=(EcObservation){0};o.lifecycle=EC_RUNNING;o.allow_afterfire=1;
    o.rpm=4000;o.load=.7;o.previous_gear=2;o.overrun_strength=.8;
    ec_observe(&s,&o,0);o.shifts=1;o.overruns=1;ec_observe(&s,&o,2160);
    CHECK(s.count>=2&&!ec_poll(&s,2400,&cmd));
    o.lifecycle=EC_STOPPING;ec_observe(&s,&o,2400);stops=releases=0;
    while(ec_poll(&s,48000,&cmd)) {
        if(cmd.operation==EC_START){CHECK(cmd.type==ES_STOP);++stops;}
        else {CHECK(cmd.type!=ES_STOP&&cmd.release_seconds==.02);++releases;}
    }
    CHECK(stops==1&&releases==6&&!s.overflow);
    /* An explicit audition made after OFF remains available. */
    o.lifecycle=EC_OFF;ec_observe(&s,&o,48000);
    c.manual_type=ES_CATCH;c.manual_sequence=1;CHECK(ec_set(&s,&c,48000));
    ec_observe(&s,&o,48000);
    CHECK(ec_poll(&s,48000,&cmd)&&cmd.operation==EC_START&&cmd.type==ES_CATCH&&cmd.manual);
    CHECK(!ec_poll(&s,96000,&cmd));return 0;
}
static int check_full_automatic_queue(void) {
    EcState s;EcControl c=ec_default();EcObservation o={0};EcCommand cmd;
    unsigned released=0,stops=0,overflow;
    ec_init(&s,127);c.enabled=1;CHECK(ec_set(&s,&c,0));
    o.lifecycle=EC_RUNNING;o.allow_afterfire=1;o.rpm=4000;o.load=-.3;o.overrun_strength=.8;
    ec_observe(&s,&o,0);
    while(s.count<EC_QUEUE){++o.overruns;ec_observe(&s,&o,2160);}
    overflow=s.overflow;CHECK(s.count==EC_QUEUE);
    o.lifecycle=EC_STOPPING;ec_observe(&s,&o,2400);
    while(ec_poll(&s,96000,&cmd)) {
        if(cmd.operation==EC_START){CHECK(cmd.type==ES_STOP);++stops;}
        else {CHECK(cmd.type>=0&&cmd.type!=ES_STOP);released|=1u<<cmd.type;}
    }
    CHECK(stops==1&&released==(127u&~(1u<<ES_STOP))&&s.overflow==overflow);
    return 0;
}
int main(void) {
    CHECK(check_stopping()==0);
    CHECK(check_full_automatic_queue()==0);
    EcState s;EcControl c=ec_default();EcCommand cmd;EcObservation o={0};unsigned count=0;
    ec_init(&s,127);CHECK(ec_set(&s,&c,0));o.lifecycle=EC_CRANK;o.starts=1;
    ec_observe(&s,&o,0);CHECK(!ec_poll(&s,1000,&cmd));
    c.enabled=1;CHECK(ec_set(&s,&c,1200));ec_observe(&s,&o,1200);
    CHECK(ec_poll(&s,1200,&cmd)&&cmd.operation==EC_START&&cmd.type==ES_ENGAGE&&cmd.request.id==1);
    CHECK(!ec_poll(&s,1583,&cmd));CHECK(ec_poll(&s,1584,&cmd)&&cmd.type==ES_CRANK&&cmd.request.id==2);
    ec_observe(&s,&o,1680);CHECK(!ec_poll(&s,1680,&cmd)); /* Holding state does not retrigger. */
    o.lifecycle=EC_CATCH;ec_observe(&s,&o,1920);
    CHECK(ec_poll(&s,1920,&cmd)&&cmd.operation==EC_RELEASE&&cmd.type==ES_CRANK);
    CHECK(ec_poll(&s,1920,&cmd)&&cmd.type==ES_DISENGAGE);
    CHECK(ec_poll(&s,1920,&cmd)&&cmd.type==ES_CATCH);
    o.lifecycle=EC_RUNNING;o.allow_afterfire=1;o.rpm=4000;o.load=-.3;o.overrun_strength=.8;
    ec_observe(&s,&o,2160);o.overruns=1;ec_observe(&s,&o,2400);
    CHECK(s.count>=1&&s.count<=3);CHECK(!ec_poll(&s,3263,&cmd));
    CHECK(ec_poll(&s,3264,&cmd)&&cmd.type==ES_AFTERFIRE&&cmd.request.requested_frame==3264);
    o.allow_afterfire=0;ec_observe(&s,&o,3360);CHECK(!ec_poll(&s,50000,&cmd)); /* Cancel future cluster, never fake an ECU. */
    c.manual_type=ES_CATCH;c.manual_sequence=1;CHECK(ec_set(&s,&c,3600));CHECK(ec_set(&s,&c,3600));
    CHECK(ec_poll(&s,3600,&cmd)&&cmd.type==ES_CATCH);CHECK(!ec_poll(&s,3600,&cmd));
    c.manual_sequence=0;CHECK(!ec_set(&s,&c,3600));c.manual_sequence=1;
    c.pitch=NAN;CHECK(!ec_set(&s,&c,3600));c.pitch=1;
    c.enabled=0;CHECK(ec_set(&s,&c,3840));CHECK(ec_poll(&s,3840,&cmd)&&cmd.operation==EC_RELEASE&&cmd.type==-1);
    /* Bounded queue and observable refusal, no allocation or unbounded burst. */
    c.enabled=1;c.manual_type=ES_CATCH;
    for(unsigned k=0;k<30;++k){++c.manual_sequence;CHECK(ec_set(&s,&c,4080));}
    CHECK(s.count==16&&s.overflow==14&&s.peak_queue==16);
    while(ec_poll(&s,4080,&cmd))++count;CHECK(count==16);
    /* A deliberate manual audition remains available while the engine is off.
       Automatic overrun qualification must only cancel automatic cluster commands. */
    ec_init(&s,127);c=ec_default();c.enabled=1;c.manual_type=ES_AFTERFIRE;c.manual_sequence=1;
    CHECK(ec_set(&s,&c,0));o=(EcObservation){0};ec_observe(&s,&o,0);
    CHECK(ec_poll(&s,0,&cmd)&&cmd.type==ES_AFTERFIRE&&cmd.manual);
    CHECK(!ec_poll(&s,48000,&cmd));
    puts("PASS semantic edge triggering, fixed-frame scheduling, manual sequence, cancellation, queue bound, invalid controls");return 0;
}
