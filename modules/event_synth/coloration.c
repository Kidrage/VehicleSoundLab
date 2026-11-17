#include "internal.h"
#include <math.h>
#include <string.h>
void es_color_init(EsColorSection s[2],double hz) {
    static const double q[2]={.541196100146197,1.3065629648763766};
    unsigned k;double w=2*ES_PI*hz/ES_RATE,c=cos(w),v=sin(w);
    memset(s,0,2*sizeof *s);
    for(k=0;k<2;++k) {
        double a=v/(2*q[k]),den=1+a;
        s[k].b0=(1-c)/(2*den);s[k].b1=(1-c)/den;s[k].b2=s[k].b0;
        s[k].a1=-2*c/den;s[k].a2=(1-a)/den;
    }
}
double es_color_tick(EsColorSection s[2],double input) {
    unsigned k;
    for(k=0;k<2;++k) {
        double output=s[k].b0*input+s[k].z1;
        s[k].z1=s[k].b1*input-s[k].a1*output+s[k].z2;
        s[k].z2=s[k].b2*input-s[k].a2*output;
        input=output;
    }
    return input;
}
