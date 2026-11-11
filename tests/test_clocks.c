#include "core/engine.h"
#include "core/modules.h"
#include <math.h>
#include <stdio.h>
#include <stdlib.h>
static int failures;
#define CHECK(x,m) do { if(!(x)) { fprintf(stderr,"FAIL: %s\n",m);++failures; } } while(0)
static void custom(VslEngine *e,double root) {
    e->dna.custom_count=1;e->dna.custom_root=root;e->dna.custom_amp[0]=1;
}
int main(void) {
    VslEngine *a=malloc(sizeof *a),*b=malloc(sizeof *b);
    float x[480],y[480],sa[240*VSL_OBJECTS],sb[240*VSL_OBJECTS];
    VslParams p=vsl_default_params(0);int i,c,block,test;
    double mechanical=0,air=0;
    if(!a||!b) { free(a);free(b);return 2; }
    p.rpm=5000;p.load=.7;p.space=0;
    vsl_init(a,48000,48271);vsl_init(b,48000,48271);
    a->smooth.space=b->smooth.space=0;custom(a,55);custom(b,220);
    vsl_set_params(a,&p);vsl_set_params(b,&p);
    for(block=0;block<500;++block) {
        vsl_process_layout(a,x,240,2,sa);vsl_process_layout(b,y,240,2,sb);
        CHECK(a->control.phase==b->control.phase && a->detail.variation_phase==b->detail.variation_phase,
            "imported root never retimes the crank or variation clock");
        for(i=0;i<240;++i)for(c=VSL_INTAKE;c<VSL_OBJECTS;++c)
            CHECK(sa[i*VSL_OBJECTS+c]==sb[i*VSL_OBJECTS+c],"all non-exhaust stems are root-independent with room/IR disabled");
        for(i=0;i<240;++i) { mechanical+=fabs(sa[i*VSL_OBJECTS+VSL_MECHANICAL]);air+=fabs(sa[i*VSL_OBJECTS+VSL_AIR_L]); }
    }
    CHECK(mechanical>1 && air>1,"independence is verified on active mechanical and combustion-modulated NVH voices");
    for(test=0;test<2;++test) {
        double re=0,im=0,wrong=0,hz=test?110:55;
        vsl_init(a,48000,48271);custom(a,55);a->control.rpm=test?6000:3000;
        a->voice.dna_gain=1;vsl_dna_update(a);
        for(i=0;i<96000;++i) {
            double l,r,ph=2*VSL_PI*hz*(i+1)/48000;
            vsl_clocks_tick(a);vsl_dna_tick(a,&l,&r);
            if(i>=48000) { re+=l*cos(ph);im-=l*sin(ph);wrong+=l*cos(ph*1.5); }
        }
        CHECK(2*hypot(re,im)/48000>.3,"imported oscillator retains root at 3000 RPM and octave at 6000 RPM");
        CHECK(fabs(2*wrong/48000)<.0001,"custom pitch does not leak the unrelated crank fundamental");
    }
    free(a);free(b);
    if(!failures)puts("PASS: independent crank/DNA clocks, active stem invariance and actual imported pitch law");
    return failures?1:0;
}
