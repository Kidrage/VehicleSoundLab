#ifndef VSL_DSP_FAST_TRIG_H
#define VSL_DSP_FAST_TRIG_H
#include <math.h>
#define VSL_TRIG_SIZE 2048
extern float vsl_trig_table[VSL_TRIG_SIZE+1];
extern int vsl_trig_ready;
void vsl_trig_prepare(void);
/* A split 2*pi keeps the small, bounded audio-phase reduction accurate.
   Larger/exceptional arguments use the vendor library's general reducer. */
static inline float vsl_trig_lookup(float x,unsigned quarter){
    float r,t,u;int q;unsigned index;
    if(!vsl_trig_ready)vsl_trig_prepare();
    q=(int)(x*.15915494309189533577f);
    if(x>=-1024.f&&x<=1024.f)
        r=(x-q*6.28125f)-q*.001935307179586476925f;
    else {
        int hi=(q/256)*256,lo=q-hi;
        r=((x-hi*6.28125f)-lo*6.28125f);
        r-=hi*.001922607421875f;
        r-=lo*.001922607421875f;
        r-=q*.000012699757711476925f;
    }
    /* The float quotient may round across an integer near a period boundary.
       A second correction covers that one-period quotient error. */
    if(r<0)r+=6.2831853071795864769f;
    if(r<0)r+=6.2831853071795864769f;
    if(r>=6.2831853071795864769f)r-=6.2831853071795864769f;
    t=r*(VSL_TRIG_SIZE/6.2831853071795864769f);
    index=(unsigned)t;u=t-index;index=(index+quarter)&(VSL_TRIG_SIZE-1);
    return vsl_trig_table[index]+u*(vsl_trig_table[index+1]-vsl_trig_table[index]);
}
static inline float vsl_fast_sinf(float x){
    if(x==0)return x;
    if(x>=-1000000.f&&x<=1000000.f)return vsl_trig_lookup(x,0);
    return sinf(x);
}
static inline float vsl_fast_cosf(float x){
    if(x>=-1000000.f&&x<=1000000.f)return vsl_trig_lookup(x,VSL_TRIG_SIZE/4);
    return cosf(x);
}
#define sinf vsl_fast_sinf
#define cosf vsl_fast_cosf
#endif
