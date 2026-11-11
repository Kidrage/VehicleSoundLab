#define _CRT_SECURE_NO_WARNINGS
#include "profile.h"
#include <math.h>
#include <string.h>
int sr_profile_valid(const SrProfile *p) {
    unsigned i;
    if(!p||p->rate!=48000||!p->bands||p->bands>SR_MAX_BANDS||p->partials<8||p->partials>SR_MAX_PARTIALS)return 0;
    for(i=0;i<p->bands;++i) {
        const SrBand *b=&p->band[i];
        if(!isfinite(b->low)||!isfinite(b->high)||b->low<20||b->high<=b->low||b->high*1.1>21600||
           (i&&b->low<p->band[i-1].high)||!isfinite(b->power[0])||!isfinite(b->power[1])||
           b->power[0]<0||b->power[1]<0||b->power[0]>4||b->power[1]>4||
           !isfinite(b->coherence[0])||!isfinite(b->coherence[1])||
           hypot(b->coherence[0],b->coherence[1])>1.000000000001)return 0;
        if((b->power[0]==0||b->power[1]==0)&&(b->coherence[0]!=0||b->coherence[1]!=0))return 0;
    }
    return 1;
}
int sr_profile_read(FILE *stream,SrProfile *profile) {
    SrProfile p={0};char tag[32],tail;unsigned version,i;
    if(!stream||!profile||fscanf(stream,"%31s %u %u %u %u",tag,&version,&p.rate,&p.bands,&p.partials)!=5||
       strcmp(tag,"VSL_SOUND_RESIDUAL")||version!=1||p.bands>SR_MAX_BANDS)return 0;
    for(i=0;i<p.bands;++i) {
        SrBand *b=&p.band[i];
        if(fscanf(stream,"%lf %lf %lf %lf %lf %lf",&b->low,&b->high,&b->power[0],&b->power[1],
                  &b->coherence[0],&b->coherence[1])!=6)return 0;
    }
    if(fscanf(stream," %c",&tail)==1||ferror(stream)||!sr_profile_valid(&p))return 0;
    *profile=p;return 1;
}
