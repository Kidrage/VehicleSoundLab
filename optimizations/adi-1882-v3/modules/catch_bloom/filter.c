#include "filter.h"
#include <math.h>
#include <string.h>
#define PI 3.14159265358979323846f
int cb_filter_init(CbFilter *s,float hz,float q) {
    float w,a,d;
    if(!s||!isfinite(hz)||!isfinite(q)||hz<20||hz>1000||q<.3f||q>8)return 0;
    memset(s,0,sizeof *s);w=2*PI*hz/48000;a=sinf(w)/(2*q);d=1+a;
    s->b0=a/d;s->b2=-a/d;s->a1=-2*cosf(w)/d;s->a2=(1-a)/d;return 1;
}
void cb_filter_tick(CbFilter *s,const float input[2],float out[2]) {
    unsigned c;for(c=0;c<2;++c){float x=input[c],y=s->b0*x+s->z1[c];
        s->z1[c]=-s->a1*y+s->z2[c];s->z2[c]=s->b2*x-s->a2*y;out[c]=y;}
}
