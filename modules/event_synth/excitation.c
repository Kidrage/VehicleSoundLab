#include "internal.h"
#include <math.h>
double es_random(uint32_t *s) {
    *s^=*s<<13;*s^=*s>>17;*s^=*s<<5;
    return 2*((double)*s/4294967296.)-1;
}
void es_noise_init(EsNoiseBand *b,const EsBand *p,const EsRequest *r) {
    double hz=fmin(21000,p->hz*r->pitch),w=2*ES_PI*hz/ES_RATE,a=sin(w)/(2*p->q),den=1+a;
    b->b0=a/den;b->b2=-b->b0;b->a1=-2*cos(w)/den;b->a2=(1-a)/den;
    b->z1=b->z2=0;b->amplitude=p->amplitude*r->texture;
    b->decay=exp(-1/(ES_RATE*p->decay_seconds*r->decay));b->attack=p->attack_seconds;
}
double es_noise_tick(EsNoiseBand *b,double noise,uint64_t age,int gated) {
    double y=b->b0*noise+b->z1;
    b->z1=-b->a1*y+b->z2;b->z2=b->b2*noise-b->a2*y;
    double x=y*b->amplitude*es_attack(age,b->attack);
    if(!gated)b->amplitude*=b->decay;
    return x;
}
