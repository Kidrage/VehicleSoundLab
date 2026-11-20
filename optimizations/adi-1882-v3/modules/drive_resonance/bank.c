#include "bank.h"
#include <math.h>
#include <string.h>
#include <stdlib.h>
#include "dsp_support/storage.h"
VSL_STORAGE(drs_scratch,DrsBank,1,VSL_DDR)
int drs_bank_valid(const DrsBank *b,const SaBank *dna) {
    unsigned i,active=0;
    if(!b||!dna||!b->count||b->count>SA_MAX_ANCHORS||b->count!=dna->count||
       !isfinite(b->outer_low)||!isfinite(b->inner_low)||!isfinite(b->inner_high)||!isfinite(b->outer_high)||
       b->outer_low<.9f||b->outer_low>=b->inner_low||b->inner_low>1||b->inner_high<1||
       b->inner_low>=b->inner_high||b->inner_high>=b->outer_high||b->outer_high>1.1f)return 0;
    for(i=0;i<b->count;++i) {
        if(!dna->profile[i]||!isfinite(b->root[i])||fabsf(b->root[i]-dna->profile[i]->base_hz)>1e-8f||b->enabled[i]>1)return 0;
        if(!b->enabled[i]){if(b->kind[i]!=DRS_NONE)return 0;continue;}
        if(b->kind[i]==DRS_RDT) {
            if(!rdt_profile_valid(b->profile+i)||fabsf(b->profile[i].base_hz-b->root[i])>1e-8f)return 0;
        } else if(b->kind[i]==DRS_STEREO) {
            if(!rvs_profile_valid(b->stereo+i)||fabsf(b->stereo[i].base_hz-b->root[i])>1e-8f)return 0;
        } else return 0;
        ++active;
    }return active>0;
}
int drs_bank_init_mixed(DrsBank *out,const SaBank *dna,const RdtProfile *const *p,const RvsProfile *const *s) {
    DrsBank *b;unsigned i;int ok=0;
    if(!out||!dna||(!p&&!s)||!dna->count||dna->count>SA_MAX_ANCHORS)return 0;
    b=drs_scratch_acquire();if(!b)return 0;
    b->count=dna->count;b->outer_low=.9f;b->inner_low=.96f;b->inner_high=1.04f;b->outer_high=1.1f;
    for(i=0;i<b->count;++i){if(!dna->profile[i]||(p&&p[i]&&s&&s[i]))goto done;b->root[i]=dna->profile[i]->base_hz;
        if(p&&p[i]){b->enabled[i]=1;b->kind[i]=DRS_RDT;b->profile[i]=*p[i];}
        if(s&&s[i]){b->enabled[i]=1;b->kind[i]=DRS_STEREO;b->stereo[i]=*s[i];}}
    if(!drs_bank_valid(b,dna))goto done;*out=*b;ok=1;
done:drs_scratch_release(b);return ok;
}
int drs_bank_init(DrsBank *out,const SaBank *dna,const RdtProfile *const *p) {return drs_bank_init_mixed(out,dna,p,NULL);}
int drs_bank_init_stereo(DrsBank *out,const SaBank *dna,const RvsProfile *const *p) {return drs_bank_init_mixed(out,dna,NULL,p);}
