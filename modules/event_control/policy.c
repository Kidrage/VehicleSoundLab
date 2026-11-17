#include "internal.h"
#include <math.h>
#include <string.h>
EcControl ec_default(void) {
    EcControl c={0};unsigned k;c.manual_type=ES_CRANK;c.gain=.5;c.pitch=c.decay=c.texture=1;
    for(k=0;k<ES_TYPES;++k)c.levels[k]=1;
    return c;
}
static int range(double v,double lo,double hi){return isfinite(v)&&v>=lo&&v<=hi;}
/* Fixed delays are nearest-frame times. Avoid .018*48000 truncating to 863.
   Random burst gaps retain the historical floor quantization below. */
static uint64_t delay_frames(double seconds){return (uint64_t)(seconds*ES_RATE+.5);}
int ec_control_valid(const EcControl *c) {
    unsigned k;
    if(!c||(c->enabled!=0&&c->enabled!=1)||c->manual_type<0||c->manual_type>=ES_TYPES||
       !range(c->gain,0,2)||!range(c->pitch,.5,2)||!range(c->decay,.25,4)||!range(c->texture,0,2))return 0;
    for(k=0;k<ES_TYPES;++k)if(!range(c->levels[k],0,2))return 0;
    return 1;
}
void ec_init(EcState *s,unsigned mask) {
    memset(s,0,sizeof *s);s->available_mask=mask&((1u<<ES_TYPES)-1);s->rng=UINT32_C(0xbc1738a5);s->control=ec_default();
    s->policy=ec_policy_default();
}
static void stopping(EcState *s,uint64_t frame) {
    unsigned k;
    /* These voices belong to the running/startup process. Stop new automatic
       starts and fade active tails, while the independent STOP event can ring.
       A manual audition begun later in OFF remains available. */
    /* Cancel every queued automatic start before inserting releases. A full
       queue of a later type must not block releases for earlier types. */
    for(k=0;k<ES_TYPES;++k)if(k!=ES_STOP)ec_cancel_automatic(s,(int)k);
    for(k=0;k<ES_TYPES;++k)if(k!=ES_STOP&&(s->available_mask&(1u<<k)))
        ec_release(s,(int)k,frame,.02);
}
int ec_set(EcState *s,const EcControl *c,uint64_t frame) {
    if(!s||!ec_control_valid(c)||c->manual_sequence<s->manual_sequence)return 0;
    if(c->enabled&&c->manual_sequence!=s->manual_sequence&&!(s->available_mask&(1u<<c->manual_type)))return 0;
    if(c->manual_sequence==s->manual_sequence&&c->manual_type!=s->control.manual_type&&c->manual_sequence)return 0;
    int was_enabled=s->control.enabled;s->control=*c;
    if(was_enabled&&!c->enabled){ec_cancel(s,-1);ec_release(s,-1,frame,.02);s->enabled_seen=0;}
    if(c->manual_sequence!=s->manual_sequence&&c->enabled) {
        ec_manual_start(s,(unsigned)c->manual_type,frame);
        if(c->manual_type==ES_CRANK)ec_release(s,ES_CRANK,frame+(uint64_t)(.8*c->decay*ES_RATE),.025);
    }
    s->manual_sequence=c->manual_sequence;
    return 1;
}
void ec_observe(EcState *s,const EcObservation *o,uint64_t frame) {
    if(!s||!o)return;
    if(!s->control.enabled){s->last=*o;s->initialized=1;return;}
    int entering=!s->enabled_seen,previous=entering?EC_OFF:s->last.lifecycle;
    s->enabled_seen=1;
    if(o->lifecycle==EC_CRANK&&previous!=EC_CRANK) {
        ec_start(s,ES_ENGAGE,frame,220,.8);ec_start(s,ES_CRANK,frame+delay_frames(s->policy.crank_delay_seconds),240,1);
    }
    if(previous==EC_CRANK&&o->lifecycle!=EC_CRANK) {
        ec_cancel(s,ES_CRANK);ec_release(s,ES_CRANK,frame,.018);
        if(o->lifecycle==EC_CATCH)ec_start(s,ES_DISENGAGE,frame,220,.6);
    }
    if(o->lifecycle==EC_CATCH&&previous!=EC_CATCH&&!entering)ec_start(s,ES_CATCH,frame,240,1);
    if(o->lifecycle==EC_STOPPING&&previous!=EC_STOPPING) {
        stopping(s,frame);
        ec_start(s,ES_STOP,frame,220,.7);
    }
    if(!o->allow_afterfire||o->lifecycle!=EC_RUNNING)ec_cancel_automatic(s,ES_AFTERFIRE);
    if(!entering&&o->overruns!=s->last.overruns&&o->allow_afterfire&&o->lifecycle==EC_RUNNING) {
        const EcPolicy *p=&s->policy;int permit=1;
        ++s->policy_stats.opportunities;
        if(s->has_burst&&frame-s->last_burst_frame<delay_frames(p->afterfire_cooldown_seconds)) {
            ++s->policy_stats.cooldown_skips;permit=0;
        } else if(p->afterfire_probability==0||(p->afterfire_probability<1&&ec_random(s)>=p->afterfire_probability)) {
            ++s->policy_stats.probability_skips;permit=0;
        }
        if(permit) {
            unsigned k,count=p->afterfire_min_count+(unsigned)((p->afterfire_max_count-p->afterfire_min_count+1)*ec_random(s));
            uint64_t at=frame+delay_frames(p->afterfire_delay_seconds);
            double strength=fmin(1,fmax(.1,o->overrun_strength));
            if(s->available_mask&(1u<<ES_AFTERFIRE)) {
                ++s->policy_stats.bursts_attempted;s->last_burst_frame=frame;s->has_burst=1;
            } else ++s->policy_stats.unavailable;
            for(k=0;k<count;++k){ec_start(s,ES_AFTERFIRE,at,100,strength);
                at+=(uint64_t)((p->afterfire_interval_min_seconds+(p->afterfire_interval_max_seconds-p->afterfire_interval_min_seconds)*ec_random(s))*ES_RATE);
                strength*=p->afterfire_repeat_gain;}
        }
    }
    if(!entering&&o->shifts!=s->last.shifts&&o->previous_gear>0&&o->rpm>1500)
        ec_start(s,ES_SHIFT,frame+delay_frames(s->policy.shift_delay_seconds),150,.4+.4*fmin(1,fabs(o->load)));
    s->last=*o;s->initialized=1;
}
