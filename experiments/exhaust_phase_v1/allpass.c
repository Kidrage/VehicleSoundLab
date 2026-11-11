#include "allpass.h"
#include <math.h>
#include <string.h>
int vsl_allpass_init(VslAllpass *s,double rate,double hz,double q) {
    double w,alpha,den;memset(s,0,sizeof *s);
    if(!isfinite(rate)||rate<16000||rate>192000||!isfinite(hz)||hz<=0||hz>=.4*rate||!isfinite(q)||q<.1||q>10)return 0;
    w=6.2831853071795864769*hz/rate;alpha=sin(w)/(2*q);den=1+alpha;
    s->a1=-2*cos(w)/den;s->a2=s->b0=(1-alpha)/den;return 1;
}
double vsl_allpass_tick(VslAllpass *s,double x) {
    double y=s->b0*x+s->z1;
    s->z1=s->a1*(x-y)+s->z2;s->z2=x-s->a2*y;
    if(fabs(s->z1)+fabs(s->z2)<1e-24)s->z1=s->z2=0;
    return y;
}
