#include "core/event_split.h"
#include <math.h>
#include <string.h>
void vsl_color_lowpass_init(VslColorLowpass *s,double rate,double hz) {
    double w=6.2831853071795864769*fmin(hz,.30*rate)/rate;
    double c=cos(w),a=sin(w)/sqrt(2.0),normal=1/(1+a);
    memset(s,0,sizeof *s);s->b0=(1-c)*.5*normal;s->b1=(1-c)*normal;s->b2=s->b0;
    s->a1=-2*c*normal;s->a2=(1-a)*normal;
}
double vsl_color_lowpass_tick(VslColorLowpass *s,double x) {
    double y=s->b0*x+s->z1;
    s->z1=s->b1*x-s->a1*y+s->z2;s->z2=s->b2*x-s->a2*y;return y;
}
