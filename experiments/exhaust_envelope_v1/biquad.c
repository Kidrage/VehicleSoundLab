#include "biquad.h"
#include <math.h>
#include <string.h>
int vsl_envelope_bell(VslEnvelopeBiquad *s,double rate,double hz,double q,double db) {
    double a,w,alpha,den;memset(s,0,sizeof *s);
    if(!isfinite(rate)||rate<16000||rate>192000||!isfinite(hz)||hz<=0||hz>=.45*rate||
       !isfinite(q)||q<.1||q>10||!isfinite(db)||fabs(db)>3.000001)return 0;
    if(db==0) { s->b0=1;return 1; }
    a=pow(10,db/40);w=6.2831853071795864769*hz/rate;alpha=sin(w)/(2*q);den=1+alpha/a;
    s->b0=(1+alpha*a)/den;s->b1=-2*cos(w)/den;s->b2=(1-alpha*a)/den;
    s->a1=s->b1;s->a2=(1-alpha/a)/den;return 1;
}
double vsl_envelope_biquad_tick(VslEnvelopeBiquad *s,double x) {
    double y=s->b0*x+s->z1;
    s->z1=s->b1*x-s->a1*y+s->z2;s->z2=s->b2*x-s->a2*y;
    if(fabs(s->z1)+fabs(s->z2)<1e-24)s->z1=s->z2=0;
    return y;
}
