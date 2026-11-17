#include "internal.h"
#include <string.h>
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
static void start(EcState *s,unsigned type,uint64_t frame,unsigned priority,double strength,unsigned manual) {
    EcCommand c={0};
    if(type>=ES_TYPES||!(s->available_mask&(1u<<type)))return;
    c.frame=frame;c.operation=EC_START;c.type=(int)type;c.manual=manual;
    c.request=(EsRequest){++s->next_id,frame,type,priority,(uint32_t)(ec_random(s)*4294967296.),
        strength,s->control.pitch,s->control.decay,s->control.texture};
    ec_enqueue(s,&c);
}
void ec_start(EcState *s,unsigned type,uint64_t frame,unsigned priority,double strength){start(s,type,frame,priority,strength,0);}
void ec_manual_start(EcState *s,unsigned type,uint64_t frame){start(s,type,frame,180,1,1);}
void ec_release(EcState *s,int type,uint64_t frame,double seconds) {
    EcCommand c={0};c.frame=frame;c.operation=EC_RELEASE;c.type=type;c.release_seconds=seconds;
    ec_enqueue(s,&c);
}
