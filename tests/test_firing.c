#include "core/engine.h"
#include "core/modules.h"
#include "profiles/firing.h"
#include <math.h>
#include <stdio.h>
#include <stdlib.h>
static int failures;
#define CHECK(x,m) do { if(!(x)) { fprintf(stderr,"FAIL: %s\n",m);++failures; } } while(0)
int main(void) {
    VslEngine *e=malloc(sizeof *e);double left[9600],right[9600];int i,n,p;
    if(!e)return 2;
    for(i=0;i<10;++i) {
        double current=vsl_firing_degrees(VSL_V10,i,10);
        double next=i==9?720:vsl_firing_degrees(VSL_V10,i+1,10);
        CHECK(next-current==(i%2?54:90),"common-pin event gaps alternate 90/54 and close a full 720-degree cycle");
        if(i<8)CHECK(vsl_firing_degrees(VSL_V10,i+2,10)-current==144,"each five-cylinder bank keeps 144-degree spacing");
    }
    /* Pair interference without manifold delay or cylinder imbalance. */
    for(n=1;n<=8;++n) {
        double re=0,im=0,angle;
        for(i=0;i<10;++i) {
            angle=2*VSL_PI*n*5*vsl_firing_degrees(VSL_V10,i,10)/720;
            re+=cos(angle)/5;im-=sin(angle)/5;
        }
        CHECK(fabs(hypot(re,im)-2*fabs(cos(VSL_PI*n*90/144)))<1e-12,"common-pin impulse spectrum follows analytic pair interference");
        if(n==1)CHECK(hypot(re,im)>.7,"odd bank harmonics are not erroneously cancelled as in an even-fire engine");
    }
    for(p=VSL_V8;p<VSL_PROFILE_COUNT;++p)for(i=0;i<vsl_profile(p)->cylinders;++i)
        CHECK(vsl_firing_degrees(p,i,vsl_profile(p)->cylinders)==720.0*i/vsl_profile(p)->cylinders,
            "other engineering templates retain their existing event timing");
    vsl_init(e,48000,48271);e->control.rpm=2400;e->voice.dna_gain=1;
    e->smooth.irregularity=0; /* Isolate geometry from intentional AM sidebands. */
    vsl_dna_update(e);
    for(i=0;i<19200;++i) {
        double l,r;e->control.phase=fmod(2*VSL_PI*20*i/48000,2*VSL_PI);vsl_dna_tick(e,&l,&r);
        if(i>=9600) { left[i-9600]=l;right[i-9600]=r; }
    }
    for(n=1;n<=20;++n) {
        double lr=0,li=0,rr=0,ri=0,expected,error;
        for(i=0;i<9600;++i) {
            double ph=2*VSL_PI*100*n*i/48000;
            lr+=left[i]*cos(ph);li-=left[i]*sin(ph);
            rr+=right[i]*cos(ph);ri-=right[i]*sin(ph);
        }
        expected=-2*VSL_PI*n*(90.0/144)-2*VSL_PI*100*n*vsl_profile(VSL_V10)->bank_delay;
        error=atan2(sin(atan2(ri,rr)-atan2(li,lr)-expected),cos(atan2(ri,rr)-atan2(li,lr)-expected));
        CHECK(hypot(lr,li)>.01 && hypot(rr,ri)>.01,"low DNA test measures active bank harmonics");
        CHECK(fabs(error)<.00001,"actual low DNA output uses the common-pin phase and a separate physical-time delay");
    }
    free(e);
    if(!failures)puts("PASS: 720-degree closure, 90/54 bank geometry, analytic interference and rendered low-order bank phase");
    return failures?1:0;
}
