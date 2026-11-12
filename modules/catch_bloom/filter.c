#include "filter.h"
#include <math.h>
#include <string.h>
#define PI 3.14159265358979323846
int cb_filter_init(CbFilter *s,double hz,double q) {
    double w,a,d;
    if(!s||!isfinite(hz)||!isfinite(q)||hz<20||hz>1000||q<.3||q>8)return 0;
    memset(s,0,sizeof *s);w=2*PI*hz/48000;a=sin(w)/(2*q);d=1+a;
    s->b0=a/d;s->b2=-a/d;s->a1=-2*cos(w)/d;s->a2=(1-a)/d;return 1;
}
void cb_filter_tick(CbFilter *s,const double input[2],double out[2]) {
    unsigned c;for(c=0;c<2;++c){double x=input[c],y=s->b0*x+s->z1[c];
        s->z1[c]=-s->a1*y+s->z2[c];s->z2[c]=s->b2*x-s->a2*y;out[c]=y;}
}
