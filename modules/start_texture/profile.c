#define _CRT_SECURE_NO_WARNINGS
#include "profile.h"
#include <math.h>
#include <string.h>
int st_profile_valid(const StProfile *p) {
    unsigned i;
    if(!(p && sr_profile_valid(&p->spectrum) &&
        isfinite(p->attack_seconds) && p->attack_seconds >= 1./48000 && p->attack_seconds <= .5 &&
        isfinite(p->release_seconds) && p->release_seconds >= 1./48000 && p->release_seconds <= 2))return 0;
    if(p->has_finish!=0&&p->has_finish!=1)return 0;
    if(!p->has_finish)return 1;
    if(!sr_profile_valid(&p->finish)||p->spectrum.bands!=p->finish.bands||p->spectrum.partials!=p->finish.partials)return 0;
    for(i=0;i<p->spectrum.bands;++i)if(p->spectrum.band[i].low!=p->finish.band[i].low||p->spectrum.band[i].high!=p->finish.band[i].high)return 0;
    return 1;
}
int st_profile_read(FILE *f, StProfile *out) {
    StProfile p={0};char tag[32],tail;unsigned version,i;
    if(!f||!out||fscanf(f,"%31s %u %lf %lf",tag,&version,&p.attack_seconds,&p.release_seconds)!=4||
       strcmp(tag,"VSL_START_TEXTURE"))return 0;
    if(version==1) {if(!sr_profile_read(f,&p.spectrum))return 0;}
    else if(version==2) {
        if(fscanf(f,"%u %u %u",&p.spectrum.rate,&p.spectrum.bands,&p.spectrum.partials)!=3||p.spectrum.bands>SR_MAX_BANDS)return 0;
        p.has_finish=1;p.finish.rate=p.spectrum.rate;p.finish.bands=p.spectrum.bands;p.finish.partials=p.spectrum.partials;
        for(i=0;i<p.spectrum.bands;++i) {
            SrBand *a=&p.spectrum.band[i],*b=&p.finish.band[i];
            if(fscanf(f,"%lf %lf %lf %lf %lf %lf %lf %lf %lf %lf",&a->low,&a->high,&a->power[0],&a->power[1],
                &a->coherence[0],&a->coherence[1],&b->power[0],&b->power[1],&b->coherence[0],&b->coherence[1])!=10)return 0;
            b->low=a->low;b->high=a->high;
        }
        if(fscanf(f," %c",&tail)==1||ferror(f))return 0;
    } else return 0;
    if(!st_profile_valid(&p))return 0;
    *out=p;return 1;
}
