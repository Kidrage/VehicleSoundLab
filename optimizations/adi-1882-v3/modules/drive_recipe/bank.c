#include "bank.h"
#include <math.h>
#include <stdlib.h>
#include "dsp_support/storage.h"
#include <string.h>
VSL_STORAGE(drc_scratch,DrcBank,1,VSL_DDR)
static float reduction(const RssColour *p,float hz) {
    float u=(hz-p->low_hz)/(p->high_hz-p->low_hz);
    if(u<=0)return 0;if(u>1)u=1;u=u*u*(3-2*u);return p->power_reduction*u;
}
static int colour_valid(const RssColour *p) {
    return isfinite(p->power_reduction)&&p->power_reduction>=0&&p->power_reduction<1&&
        isfinite(p->low_hz)&&isfinite(p->high_hz)&&p->low_hz>=20&&
        p->high_hz>p->low_hz&&p->high_hz<=21600;
}
int drc_bank_valid(const DrcBank *b,const SaBank *dna,const DrsBank *detail) {
    unsigned a,h,active=0;
    if(!b||!dna||!dna->count||dna->count>SA_MAX_ANCHORS||!dna->harmonics||
       dna->harmonics>SD_MAX_HARMONICS||b->count!=dna->count||
       !isfinite(b->outer_low)||!isfinite(b->inner_low)||!isfinite(b->inner_high)||!isfinite(b->outer_high)||
       b->outer_low<.9f||b->outer_low>=b->inner_low||b->inner_low>1||b->inner_high<1||
       b->inner_low>=b->inner_high||b->inner_high>=b->outer_high||b->outer_high>1.1f)return 0;
    if(detail&&(!drs_bank_valid(detail,dna)||b->outer_low!=detail->outer_low||
       b->inner_low!=detail->inner_low||b->inner_high!=detail->inner_high||b->outer_high!=detail->outer_high))return 0;
    for(a=0;a<b->count;++a) {
        if(!dna->profile[a]||b->root[a]!=dna->profile[a]->base_hz||b->has_low[a]>1||
           !isfinite(b->scale[a])||b->scale[a]<0||b->scale[a]>4||!colour_valid(b->colour+a))return 0;
        if(b->colour[a].power_reduction>0) {
            if(!detail||!detail->enabled[a]||
               (detail->kind[a]!=DRS_RDT&&detail->kind[a]!=DRS_STEREO))return 0;
            ++active;
        }
        /* Additive detail is a complete recipe too: no DNA withdrawal and
           no independent LF are required. drs_bank_valid checked its kernel. */
        if(detail&&detail->enabled[a])++active;
        if(b->has_low[a]) {
            if(!rss_profile_valid(b->low+a)||b->low[a].base_hz!=b->root[a])return 0;
            ++active;
        }
        for(h=0;h<dna->harmonics;++h)if(!isfinite(b->reduction[a][h])||
            b->reduction[a][h]!=reduction(b->colour+a,(h+1)*b->root[a]))return 0;
    }
    return active>0;
}
int drc_bank_init(DrcBank *out,const SaBank *dna,const DrsBank *detail,
    const RssColour *colour,const SdProfile *const *low,const float *scale) {
    DrcBank *b;unsigned a,h;int ok=0;
    if(!out||!dna||!dna->count||dna->count>SA_MAX_ANCHORS||!dna->harmonics||
       dna->harmonics>SD_MAX_HARMONICS||!colour)return 0;
    b=drc_scratch_acquire();if(!b)return 0;
    b->count=dna->count;b->outer_low=.9f;b->inner_low=.96f;b->inner_high=1.04f;b->outer_high=1.1f;
    if(detail){b->outer_low=detail->outer_low;b->inner_low=detail->inner_low;
        b->inner_high=detail->inner_high;b->outer_high=detail->outer_high;}
    for(a=0;a<b->count;++a) {
        if(!dna->profile[a]||!colour_valid(colour+a))goto done;
        b->root[a]=dna->profile[a]->base_hz;b->colour[a]=colour[a];b->scale[a]=scale?scale[a]:1;
        if(low&&low[a]){b->low[a]=*low[a];b->has_low[a]=1;}
        for(h=0;h<dna->harmonics;++h)b->reduction[a][h]=reduction(colour+a,(h+1)*b->root[a]);
    }
    if(!drc_bank_valid(b,dna,detail))goto done;*out=*b;ok=1;
done:drc_scratch_release(b);return ok;
}
