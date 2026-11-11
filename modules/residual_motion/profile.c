#define _CRT_SECURE_NO_WARNINGS
#include "profile.h"
#include <math.h>
#include <string.h>
int rm_profile_valid(const RmProfile *p) {
    unsigned b,k;
    if(!p||!p->bands||p->bands>SR_MAX_BANDS||p->factors>RM_MAX_FACTORS)return 0;
    for(k=0;k<p->factors;++k)if(!isfinite(p->rho[k])||p->rho[k]<0||p->rho[k]>.95)return 0;
    for(b=0;b<p->bands;++b) {
        double bound=0;
        if(!isfinite(p->low[b])||!isfinite(p->high[b])||p->low[b]<20||p->high[b]<=p->low[b]||
           p->high[b]*1.1>21600||(b&&p->low[b]<p->high[b-1]))return 0;
        for(k=0;k<p->factors;++k) {
            if(!isfinite(p->basis[b][k]))return 0;
            bound+=fabs(p->basis[b][k])*sqrt((1+p->rho[k])/(1-p->rho[k]));
        }
        if(!isfinite(bound)||bound>.750000000001)return 0;
    }
    return 1;
}
int rm_profile_matches(const RmProfile *m,const SrProfile *p) {
    unsigned b;if(!rm_profile_valid(m)||!sr_profile_valid(p)||m->bands!=p->bands)return 0;
    for(b=0;b<m->bands;++b)if(m->low[b]!=p->band[b].low||m->high[b]!=p->band[b].high)return 0;
    return 1;
}
int rm_profile_read(FILE *stream,RmProfile *profile) {
    RmProfile p={0};char tag[32],tail;unsigned version,rate,hop,b,k;
    if(!stream||!profile||fscanf(stream,"%31s %u %u %u %u %u",tag,&version,&rate,&hop,&p.bands,&p.factors)!=6||
       strcmp(tag,"VSL_RESIDUAL_MOTION")||version!=1||rate!=48000||hop!=480||
       p.bands>SR_MAX_BANDS||p.factors>RM_MAX_FACTORS)return 0;
    for(k=0;k<p.factors;++k)if(fscanf(stream,"%lf",p.rho+k)!=1)return 0;
    for(b=0;b<p.bands;++b) {
        if(fscanf(stream,"%lf %lf",p.low+b,p.high+b)!=2)return 0;
        for(k=0;k<p.factors;++k)if(fscanf(stream,"%lf",&p.basis[b][k])!=1)return 0;
    }
    if(fscanf(stream," %c",&tail)==1||ferror(stream)||!rm_profile_valid(&p))return 0;
    *profile=p;return 1;
}
