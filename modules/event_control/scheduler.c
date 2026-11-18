#include "internal.h"
#include <string.h>
#include <math.h>
int ec_enqueue(EcState *s,const EcCommand *c) {
    unsigned at=s->count;
    if(s->count==EC_QUEUE){++s->overflow;return 0;}
    while(at&&s->queue[at-1].frame>c->frame){s->queue[at]=s->queue[at-1];--at;}
    s->queue[at]=*c;++s->count;
    if(s->count>s->peak_queue)s->peak_queue=s->count;
    return 1;
}
static void cancel(EcState *s,int type,int automatic_only) {
    unsigned read,write=0;
    for(read=0;read<s->count;++read) {
        EcCommand *c=s->queue+read;
        if(c->operation==EC_START&&(type<0||c->type==type)&&(!automatic_only||!c->manual)){++s->cancelled;continue;}
        s->queue[write++]=*c;
    }
    s->count=write;
}
void ec_cancel(EcState *s,int type){cancel(s,type,0);}
void ec_cancel_automatic(EcState *s,int type){cancel(s,type,1);}
int ec_poll(EcState *s,uint64_t frame,EcCommand *out) {
    if(!s||!out||!s->count||s->queue[0].frame>frame)return 0;
    *out=s->queue[0];--s->count;memmove(s->queue,s->queue+1,s->count*sizeof *s->queue);return 1;
}
double ec_random(EcState *s) {
    s->rng^=s->rng<<13;s->rng^=s->rng>>17;s->rng^=s->rng<<5;
    return s->rng/4294967296.;
}
static void start_scaled(EcState *s,unsigned type,uint64_t frame,unsigned priority,double strength,unsigned manual,double pitch,double decay) {
    EcCommand c={0};
    if(type>=ES_TYPES||!(s->available_mask&(1u<<type)))return;
    c.frame=frame;c.operation=EC_START;c.type=(int)type;c.manual=manual;
    c.request=(EsRequest){++s->next_id,frame,type,priority,(uint32_t)(ec_random(s)*4294967296.),
        fmin(4,fmax(0,strength)),fmin(2.6,fmax(.5,s->control.pitch*pitch)),fmin(5.2,fmax(.25,s->control.decay*decay)),s->control.texture};
    ec_enqueue(s,&c);
}
static void start(EcState *s,unsigned type,uint64_t frame,unsigned priority,double strength,unsigned manual) {
    start_scaled(s,type,frame,priority,strength,manual,1,1);
}
void ec_start(EcState *s,unsigned type,uint64_t frame,unsigned priority,double strength){start(s,type,frame,priority,strength,0);}
void ec_manual_start(EcState *s,unsigned type,uint64_t frame){start(s,type,frame,180,1,1);}
void ec_afterfire_burst(EcState *s,uint64_t frame,double strength,unsigned manual) {
    const EcPolicy *p=&s->policy;unsigned k;
    unsigned count=p->afterfire_min_count+(unsigned)((p->afterfire_max_count-p->afterfire_min_count+1)*ec_random(s));
    uint64_t at=frame+(manual?0:(uint64_t)(p->afterfire_delay_seconds*ES_RATE+.5));
    int extended=p->afterfire_max_count>4;
    for(k=0;k<count;++k) {
        if(extended) {
            /* Per-onset variation only; no sample-rate modulation or new
               voices. Old <=4-pop recipes preserve their original RNG path. */
            double accent=k==0?1:(.60+.40*ec_random(s));
            double pitch=.92+.16*ec_random(s),decay=.78+.30*ec_random(s);
            start_scaled(s,ES_AFTERFIRE,at,manual?180:100,strength*accent,manual,pitch,decay);
        } else start(s,ES_AFTERFIRE,at,manual?180:100,strength,manual);
        at+=(uint64_t)((p->afterfire_interval_min_seconds+(p->afterfire_interval_max_seconds-p->afterfire_interval_min_seconds)*ec_random(s))*ES_RATE);
        strength*=p->afterfire_repeat_gain;
    }
}
void ec_release(EcState *s,int type,uint64_t frame,double seconds) {
    EcCommand c={0};c.frame=frame;c.operation=EC_RELEASE;c.type=type;c.release_seconds=seconds;
    ec_enqueue(s,&c);
}
