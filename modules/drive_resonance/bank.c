#include "bank.h"
#include <math.h>
#include <string.h>
int drs_bank_valid(const DrsBank *b,const SaBank *dna) {
    unsigned i,active=0;
    if(!b||!dna||!b->count||b->count>SA_MAX_ANCHORS||b->count!=dna->count||
       !isfinite(b->outer_low)||!isfinite(b->inner_low)||!isfinite(b->inner_high)||!isfinite(b->outer_high)||
       b->outer_low<.9||b->outer_low>=b->inner_low||b->inner_low>1||b->inner_high<1||
       b->inner_low>=b->inner_high||b->inner_high>=b->outer_high||b->outer_high>1.1)return 0;
    for(i=0;i<b->count;++i) {
        if(!dna->profile[i]||!isfinite(b->root[i])||fabs(b->root[i]-dna->profile[i]->base_hz)>1e-8||b->enabled[i]>1)return 0;
        if(b->enabled[i]){if(!rdt_profile_valid(b->profile+i)||fabs(b->profile[i].base_hz-b->root[i])>1e-8)return 0;++active;}
    }return active>0;
}
int drs_bank_init(DrsBank *out,const SaBank *dna,const RdtProfile *const *p) {
    DrsBank b;unsigned i;
    if(!out||!dna||!p||!dna->count||dna->count>SA_MAX_ANCHORS)return 0;
    memset(&b,0,sizeof b);b.count=dna->count;b.outer_low=.9;b.inner_low=.96;b.inner_high=1.04;b.outer_high=1.1;
    for(i=0;i<b.count;++i){if(!dna->profile[i])return 0;b.root[i]=dna->profile[i]->base_hz;
        if(p[i]){b.enabled[i]=1;b.profile[i]=*p[i];}}
    if(!drs_bank_valid(&b,dna))return 0;*out=b;return 1;
}
