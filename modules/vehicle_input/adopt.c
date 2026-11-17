#include "types.h"
#include <string.h>
static int same(const ViInput *a,const ViInput *b) {
    return a->valid==b->valid&&a->speed_mps==b->speed_mps&&
        a->acceleration_mps2==b->acceleration_mps2&&a->tire_slip==b->tire_slip;
}
int vi_accept(ViState *s,const ViInput *p,uint64_t frame) {
    if(!s||!vi_valid(p))return 0;
    if(s->seen&&s->value.source==p->source) {
        if(p->sequence<s->value.sequence)return 0;
        if(p->sequence==s->value.sequence)return same(p,&s->value);
    }
    s->value=*p;s->accepted_frame=frame;s->seen=1;return 1;
}
ViAdopted vi_at(const ViState *s,uint64_t frame,uint64_t max_age) {
    ViAdopted a;memset(&a,0,sizeof a);if(!s||!s->seen)return a;
    a.value=s->value;a.stale=(s->value.source==VI_EXTERNAL||(s->value.valid&VI_SLIP))&&
        (frame<s->accepted_frame||frame-s->accepted_frame>max_age);
    if(!(a.value.valid&VI_SLIP))a.value.tire_slip=0;
    if(a.stale){a.value.acceleration_mps2=0;a.value.tire_slip=0;}
    return a;
}
