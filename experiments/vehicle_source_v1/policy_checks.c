#include "event_control/api.h"
#include <assert.h>
#include <math.h>
#include <stdio.h>
static void init(EcState *s,EcPolicy p,unsigned mask) {
    EcControl c=ec_default();EcObservation o={0};c.enabled=1;ec_init(s,mask);s->policy=p;
    assert(ec_set(s,&c,0));o.lifecycle=EC_RUNNING;o.allow_afterfire=1;o.rpm=4000;o.overrun_strength=.8;
    ec_observe(s,&o,0);
}
static void lift(EcState *s,unsigned count,uint64_t at) {
    EcObservation o=s->last;o.overruns=count;ec_observe(s,&o,at);
}
int main(void) {
    EcState s;EcPolicy p=ec_policy_default(),bad;EcCommand c;unsigned i;
    assert(ec_policy_valid(&p));bad=p;bad.afterfire_min_count=0;assert(!ec_policy_valid(&bad));
    init(&s,p,1u<<ES_AFTERFIRE);lift(&s,1,48000);
    assert(ec_poll(&s,48864,&c)&&c.frame==48864); /* historical 18 ms = 864 frames */
    bad=p;bad.afterfire_max_count=13;assert(!ec_policy_valid(&bad));bad=p;bad.afterfire_interval_max_seconds=.02;assert(!ec_policy_valid(&bad));
    bad=p;bad.afterfire_probability=NAN;assert(!ec_policy_valid(&bad));bad=p;bad.shift_delay_seconds=INFINITY;assert(!ec_policy_valid(&bad));
    p.afterfire_min_count=p.afterfire_max_count=3;p.afterfire_delay_seconds=.04;
    p.afterfire_interval_min_seconds=p.afterfire_interval_max_seconds=.12;p.afterfire_repeat_gain=.5;
    init(&s,p,1u<<ES_AFTERFIRE);lift(&s,1,48000);
    assert(s.count==3&&s.policy_stats.opportunities==1&&s.policy_stats.bursts_attempted==1);
    for(i=0;i<3;++i){assert(ec_poll(&s,96000,&c));assert(c.type==ES_AFTERFIRE&&!c.manual);
        assert(c.frame==49920+i*5760&&c.request.requested_frame==c.frame);assert(fabs(c.request.strength-.8*pow(.5,i))<1e-12);}
    p.afterfire_probability=0;init(&s,p,1u<<ES_AFTERFIRE);lift(&s,1,48000);
    assert(!s.count&&s.policy_stats.probability_skips==1);
    {EcControl manual=s.control;manual.manual_type=ES_AFTERFIRE;manual.manual_sequence=1;
     assert(ec_set(&s,&manual,50000));assert(ec_poll(&s,50000,&c)&&c.manual&&c.frame==50000);}
    p.afterfire_probability=1;p.afterfire_cooldown_seconds=2;init(&s,p,1u<<ES_AFTERFIRE);
    lift(&s,1,48000);while(ec_poll(&s,100000,&c)){}lift(&s,2,96000);
    assert(!s.count&&s.policy_stats.cooldown_skips==1);lift(&s,3,144000);
    assert(s.count==3&&s.policy_stats.bursts_attempted==2&&s.policy_stats.opportunities==3);
    init(&s,p,0);lift(&s,1,48000);assert(!s.count&&s.policy_stats.unavailable==1&&!s.policy_stats.bursts_attempted);
    p=ec_policy_default();p.shift_delay_seconds=.025;p.crank_delay_seconds=.02;init(&s,p,1u<<ES_SHIFT);
    {EcObservation o=s.last;o.shifts=1;o.previous_gear=2;ec_observe(&s,&o,2000);
     assert(ec_poll(&s,4000,&c)&&c.frame==3200&&c.type==ES_SHIFT);}
    init(&s,p,(1u<<ES_TYPES)-1);
    {EcObservation o=s.last;o.lifecycle=EC_CRANK;ec_observe(&s,&o,1000);
     assert(ec_poll(&s,1000,&c)&&c.type==ES_ENGAGE);assert(ec_poll(&s,2000,&c)&&c.type==ES_CRANK&&c.frame==1960);}
    p.afterfire_min_count=p.afterfire_max_count=4;init(&s,p,(1u<<ES_TYPES)-1);lift(&s,1,48000);
    assert(s.count==4);
    {EcObservation o=s.last;o.lifecycle=EC_STOPPING;ec_observe(&s,&o,48001);
     while(ec_poll(&s,200000,&c))assert(c.operation!=EC_START||c.type==ES_STOP);}
    p=ec_policy_default();p.afterfire_min_count=p.afterfire_max_count=12;
    p.afterfire_interval_min_seconds=p.afterfire_interval_max_seconds=.04;
    init(&s,p,1u<<ES_AFTERFIRE);lift(&s,1,48000);assert(s.count==12&&!s.overflow);
    for(i=0;i<12;++i){assert(ec_poll(&s,100000,&c));assert(c.frame==48864+i*1920);
        assert(c.request.pitch>=.92&&c.request.pitch<=1.08&&c.request.decay>=.78&&c.request.decay<=1.08);}
    {EcControl manual=s.control;manual.manual_type=ES_AFTERFIRE;manual.manual_sequence=1;
     assert(ec_set(&s,&manual,100000));assert(s.count==12);
     for(i=0;i<12;++i){assert(ec_poll(&s,200000,&c)&&c.manual);assert(c.frame==100000+i*1920);}}
    puts("event policy recipe: bounded 12-onset bursts, unchanged four-voice capacity, exact frames, probability, cooldown, manual and stop isolation passed");return 0;
}
