#ifdef NDEBUG
#undef NDEBUG
#endif
#include "transfer.h"
#include <assert.h>
#include <math.h>
#include <stdlib.h>
#include <stdio.h>
#include <string.h>
static void analytic(void) {
    double rates[]={16000,48000,192000};int r;unsigned i;
    for(r=0;r<3;++r) {
        VslAllpass s;double rate=rates[r],energy=0;assert(vsl_allpass_init(&s,rate,1250,1.4));
        for(i=0;i<(unsigned)(rate*.5);++i) { double y=vsl_allpass_tick(&s,i==0?1:0);assert(isfinite(y));energy+=y*y; }
        assert(fabs(energy-1)<1e-10&&fabs(s.z1)+fabs(s.z2)<1e-20);
    }
}
static void integration(int channels,int mode) {
    VslEngine *a=malloc(sizeof *a),*b=malloc(sizeof *b);VslExhaustTransfer transfer;VslParams p=vsl_default_params(0);
    float aa[257*12],bb[257*12],sa[257*VSL_OBJECTS],sb[257*VSL_OBJECTS];unsigned k,i,changed=0;int c;
    assert(a&&b);vsl_init(a,48000,48271);vsl_init(b,48000,48271);assert(vsl_phase_init(&transfer,48000,mode));
    p.rpm=6000;p.load=.85;vsl_set_params(a,&p);vsl_set_params(b,&p);
    for(k=0;k<500;++k) {
        assert(vsl_process_layout(a,aa,257,channels,sa));assert(vsl_phase_process_layout(b,&transfer,bb,257,channels,sb));
        assert(!memcmp(&a->drive,&b->drive,sizeof a->drive));assert(!memcmp(&a->character,&b->character,sizeof a->character));
        assert(!memcmp(&a->combustion,&b->combustion,sizeof a->combustion));
        if(!mode)assert(!memcmp(aa,bb,257*channels*sizeof(float)));
        for(i=0;i<257;++i)for(c=0;c<VSL_OBJECTS;++c) {
            assert(isfinite(sb[i*VSL_OBJECTS+c]));
            if(c!=VSL_EXHAUST_L&&c!=VSL_EXHAUST_R&&c!=VSL_BODY)assert(sa[i*VSL_OBJECTS+c]==sb[i*VSL_OBJECTS+c]);
            if(sa[i*VSL_OBJECTS+c]!=sb[i*VSL_OBJECTS+c])++changed;
        }
    }
    assert(mode?changed>1000:changed==0);free(a);free(b);
}
static void layouts(void) {
    VslEngine *a=malloc(sizeof *a),*b=malloc(sizeof *b);VslExhaustTransfer ta,tb;
    VslParams p=vsl_default_params(0);float aa[257*2],bb[257*12],sa[257*10],sb[257*10];unsigned k;
    assert(a&&b);vsl_init(a,48000,48271);vsl_init(b,48000,48271);p.rpm=8000;
    vsl_set_params(a,&p);vsl_set_params(b,&p);assert(vsl_phase_init(&ta,48000,3)&&vsl_phase_init(&tb,48000,3));
    for(k=0;k<400;++k) {
        assert(vsl_phase_process_layout(a,&ta,aa,257,2,sa)&&vsl_phase_process_layout(b,&tb,bb,257,12,sb));
        assert(!memcmp(sa,sb,sizeof sa));assert(!memcmp(&ta,&tb,sizeof ta));
    }
    free(a);free(b);
}
static void bypass(void) {
    VslEngine *e=malloc(sizeof *e);VslExhaustTransfer s;VslObjectFrame o;int mode,variant,c;
    assert(e);vsl_init(e,48000,48271);
    for(mode=1;mode<4;++mode)for(variant=0;variant<3;++variant) {
        assert(vsl_phase_init(&s,48000,mode));e->smooth.profile=variant==0?VSL_V8:VSL_V10;
        e->dna.custom_count=variant==1;e->target.pure_osc=variant==2;
        for(c=0;c<VSL_OBJECTS;++c)o.sample[c]=.123+c*.01;
        { VslObjectFrame before=o;vsl_phase_tick(&s,e,&o);assert(!memcmp(&before,&o,sizeof o)); }
        e->smooth.profile=VSL_V10;e->dna.custom_count=0;e->target.pure_osc=0;
        memset(&o,0,sizeof o);vsl_phase_tick(&s,e,&o);assert(o.sample[0]==0&&o.sample[1]==0);
    }
    free(e);
}
int main(void) {
    int mode;analytic();for(mode=0;mode<4;++mode) { integration(2,mode);integration(12,mode); }
    layouts();bypass();puts("phase transfer: unity energy, ringdown, instance/layout/drive independence and bypass pass");return 0;
}
