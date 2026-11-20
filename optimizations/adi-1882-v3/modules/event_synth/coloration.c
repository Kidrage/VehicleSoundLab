#include "internal.h"
#include <math.h>
#include <string.h>
void es_color_init(EsColorSection s[2],float hz) {
    static const float q[2]={.541196100146197f,1.3065629648763766f};
    unsigned k;float w=2*ES_PI*hz/ES_RATE,c=cosf(w),v=sinf(w);
    memset(s,0,2*sizeof *s);
    for(k=0;k<2;++k) {
        float a=v/(2*q[k]),den=1+a;
        s[k].b0=(1-c)/(2*den);s[k].b1=(1-c)/den;s[k].b2=s[k].b0;
        s[k].a1=-2*c/den;s[k].a2=(1-a)/den;
    }
}
float es_color_tick(EsColorSection s[2],float input) {
    unsigned k;
    for(k=0;k<2;++k) {
        float output=s[k].b0*input+s[k].z1;
        s[k].z1=s[k].b1*input-s[k].a1*output+s[k].z2;
        s[k].z2=s[k].b2*input-s[k].a2*output;
        input=output;
    }
    return input;
}
