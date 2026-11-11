#define _CRT_SECURE_NO_WARNINGS
#include "profile.h"
#include <math.h>
#include <string.h>
int oc_profile_valid(const OcProfile *p) {
    unsigned i;if(!p||p->count<2||p->count>OC_MAX_KNOTS)return 0;
    for(i=0;i<p->count;++i)if(!isfinite(p->order[i])||p->order[i]<=0||p->order[i]>OC_MAX_HARMONICS||
        (i&&p->order[i]<=p->order[i-1])||!isfinite(p->db[i])||fabs(p->db[i])>24)return 0;
    return 1;
}
int oc_profile_read(FILE *f,OcProfile *p) {
    OcProfile candidate={0};char tag[32],tail;unsigned version,i;
    if(!f||!p||fscanf(f,"%31s %u %u",tag,&version,&candidate.count)!=3||strcmp(tag,"VSL_OSC_COLOUR")||version!=1||candidate.count>OC_MAX_KNOTS)return 0;
    for(i=0;i<candidate.count;++i)if(fscanf(f,"%lf %lf",candidate.order+i,candidate.db+i)!=2)return 0;
    if(fscanf(f," %c",&tail)==1||ferror(f)||!oc_profile_valid(&candidate))return 0;*p=candidate;return 1;
}
int oc_profile_compile(const OcProfile *p,double *g,unsigned count) {
    unsigned h,i;if(!g||!count||count>OC_MAX_HARMONICS||!oc_profile_valid(p))return 0;
    for(h=0;h<count;++h) {
        double order=h+1,db=p->db[0];
        if(order>=p->order[p->count-1])db=p->db[p->count-1];
        else if(order>p->order[0])for(i=1;i<p->count;++i)if(order<=p->order[i]){
            double mix=log(order/p->order[i-1])/log(p->order[i]/p->order[i-1]);
            db=p->db[i-1]+mix*(p->db[i]-p->db[i-1]);break;}
        g[h]=pow(10,db/20);
    }
    return 1;
}
