#include "core/engine.h"
#include "core/modules.h"
#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
static int failures;
#define CHECK(x,m) do { if(!(x)) { fprintf(stderr,"FAIL: %s\n",m);++failures; } } while(0)
typedef struct { double re,im; } Complex;
static Complex coefficient(const double *x,int count,double frequency,double rate) {
    Complex z={0,0};int i;
    for(i=0;i<count;++i) { double ph=2*VSL_PI*frequency*i/rate;z.re+=x[i]*cos(ph);z.im-=x[i]*sin(ph); }
    z.re*=2./count;z.im*=2./count;return z;
}
int main(void) {
    VslEngine *e=malloc(sizeof *e);double left[9600],right[9600];int i,n;
    double bank=100,rate=48000;
    if(!e)return 2;
    vsl_init(e,rate,48271);e->smooth=vsl_default_params(VSL_V10);
    e->smooth.detail=e->smooth.dna=1;e->smooth.brightness=.5;e->voice.high_gain=1;
    e->voice.dna_gain=1;e->voice.cutoff_ratio=1;
    e->control.rpm=2400;vsl_dna_update(e);vsl_high_orders_update(e);
    for(i=0;i<19200;++i) {
        VslObjectFrame o={0};e->control.phase=fmod(2*VSL_PI*(2400./120)*i/rate,2*VSL_PI);
        vsl_high_orders_tick(e,&o);
        if(i>=9600) { left[i-9600]=o.sample[VSL_EXHAUST_L];right[i-9600]=o.sample[VSL_EXHAUST_R]; }
    }
    for(n=28;n<=45;++n) {
        Complex l=coefficient(left,9600,bank*n,rate),r=coefficient(right,9600,bank*n,rate);
        double phase=atan2(r.im,r.re)-atan2(l.im,l.re);
        double expected=-2*VSL_PI*(90.0/144)*n-2*VSL_PI*bank*n*vsl_profile(VSL_V10)->bank_delay;
        double error=atan2(sin(phase-expected),cos(phase-expected));
        CHECK(hypot(l.re,l.im)>.0001,"consecutive high bank harmonics are present, including formerly skipped orders");
        CHECK(fabs(error)<.00001,"high-bank relative phase follows firing geometry and the DNA delay in seconds");
    }
    e->smooth.detail=0;
    { VslObjectFrame o={0};vsl_high_orders_tick(e,&o);CHECK(o.sample[0]==0&&o.sample[1]==0,"high-order level zero removes the isolated layer"); }
    e->dna.custom_count=1;vsl_high_orders_update(e);
    { VslObjectFrame o={0};vsl_high_orders_tick(e,&o);CHECK(o.sample[0]==0&&o.sample[1]==0&&e->high_orders.active==0,"custom DNA bypasses and clears factory high orders"); }
    for(i=0;i<3;++i) {
        double rates[]={16000,32000,96000};
        vsl_init(e,rates[i],48271);e->control.rpm=850;e->smooth.profile=VSL_V10;
        vsl_high_orders_update(e);
        for(n=1;n<=VSL_HIGH_ORDERS;++n)if(n*850*10./240>=fmin(14000,rates[i]*.46))
            CHECK(e->high_orders.target[n-1]==0,"source band limit removes high-order targets at every supported rate");
        for(n=VSL_CONTINUATION_FIRST;n<=VSL_CONTINUATION_LAST;++n)
            if(n*850*10./240>=fmin(14000,rates[i]*.46))
                CHECK(e->high_orders.continuation_target[0][n-VSL_CONTINUATION_FIRST]==0&&
                    e->high_orders.continuation_target[1][n-VSL_CONTINUATION_FIRST]==0,"continued spectrum obeys the same source band limit");
    }
    free(e);
    if(!failures)puts("PASS: dense order support, measured bank phase, layer control, custom DNA bypass and sample-rate bounds");
    return failures?1:0;
}
