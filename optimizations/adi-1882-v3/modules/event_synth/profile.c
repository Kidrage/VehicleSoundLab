#include "api.h"
#include <math.h>
static int range(float v,float lo,float hi){return isfinite(v)&&v>=lo&&v<=hi;}
int es_profile_valid(const EsProfile *p) {
    unsigned k;
    if(!p||p->mode_count>ES_MODES||p->band_count>ES_BANDS||p->gated>1||
       !range(p->duration_seconds,.005f,30)||!range(p->attack_seconds,0,2)||
       !range(p->release_seconds,.001f,2)||!range(p->sweep_seconds,0,10)||!range(p->level,0,8)||
       (p->noise_lowpass_hz!=0&&!range(p->noise_lowpass_hz,300,18000)))return 0;
    for(k=0;k<p->mode_count;++k) {
        const EsMode *m=p->modes+k;
        if(!range(m->hz,20,18000)||!range(m->end_hz,20,18000)||!range(m->amplitude,0,4)||
           !range(m->phase,-ES_RATE,ES_RATE)||!range(m->decay_seconds,.002f,10)||
           !range(m->attack_seconds,0,2))return 0;
    }
    for(k=0;k<p->band_count;++k) {
        const EsBand *b=p->bands+k;
        if(!range(b->hz,30,16000)||!range(b->q,.15f,30)||!range(b->amplitude,0,8)||
           !range(b->attack_seconds,0,2)||!range(b->decay_seconds,.002f,10))return 0;
    }
    for(k=0;k<ES_CONTOURS;++k) {
        const EsContour *c=p->contours+k;unsigned j;
        if(!c->count)continue;
        if(c->count<2||c->count>ES_KNOTS||!range(c->low_hz,0,24000)||
           !range(c->high_hz,0,24000)||c->low_hz>=c->high_hz||c->seconds[0]!=0)return 0;
        for(j=0;j<c->count;++j)if(!range(c->seconds[j],0,30)||!range(c->gain[j],0,8)||
            (j&&c->seconds[j]<=c->seconds[j-1]))return 0;
        for(j=0;j<k;++j)if(p->contours[j].count&&c->low_hz<p->contours[j].high_hz&&
            p->contours[j].low_hz<c->high_hz)return 0;
    }
    return 1;
}
