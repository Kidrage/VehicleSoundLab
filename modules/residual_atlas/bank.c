#include "bank.h"
#include <math.h>
#include <string.h>
int ra_bank_valid(const RaBank *s) {
    unsigned a,b;
    if(!s||!s->count||s->count>RA_MAX_ANCHORS)return 0;
    for(a=0;a<s->count;++a) {
        const SrProfile *p=&s->profile[a],*first=&s->profile[0];
        if(!sr_profile_valid(p)||!isfinite(s->root[a])||s->root[a]<5||s->root[a]>1000||
           (a&&s->root[a]<=s->root[a-1])||p->bands!=first->bands||p->partials!=first->partials)return 0;
        for(b=0;b<p->bands;++b)if(p->band[b].low!=first->band[b].low||p->band[b].high!=first->band[b].high)return 0;
    }
    return 1;
}
int ra_bank_init(RaBank *s,const SrProfile *const *profiles,const double *roots,unsigned count) {
    RaBank trial;unsigned a;
    if(!s||!profiles||!roots||!count||count>RA_MAX_ANCHORS)return 0;
    memset(&trial,0,sizeof trial);trial.count=count;
    for(a=0;a<count;++a) {
        if(!profiles[a])return 0;
        trial.profile[a]=*profiles[a];trial.root[a]=roots[a];
    }
    if(!ra_bank_valid(&trial))return 0;
    *s=trial;return 1;
}
