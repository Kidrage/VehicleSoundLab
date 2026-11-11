#ifdef NDEBUG
#undef NDEBUG
#endif
#include "transfer.h"
#include <assert.h>
#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
static void filters(void) {
    double rates[]={16000,48000,192000};int r,mode,side;unsigned i;
    for(r=0;r<3;++r)for(mode=0;mode<3;++mode) {
        VslEnvelopeTransfer s;double total=0,energy=0,tail=0;assert(vsl_envelope_init(&s,rates[r],mode));
        for(i=0;i<(unsigned)rates[r];++i) {
            double y=vsl_envelope_side_tick(&s,0,i==0?1:0);assert(isfinite(y));total+=y;energy+=y*y;
            if(i>(unsigned)rates[r]/2)tail=fmax(tail,fabs(y));
        }
        assert(fabs(total-1)<1e-10&&energy<4&&tail==0);
        for(side=0;side<3;++side)assert(s.bank[0][side].z1==0&&s.bank[0][side].z2==0);
        assert(vsl_envelope_side_tick(&s,1,0)==0);
    }
}
static void integration(int mode,int channels) {
    VslEngine *a=malloc(sizeof *a),*b=malloc(sizeof *b);VslEnvelopeTransfer sa,sb;
    float aa[257*12],bb[257*12],oa[257*10],ob[257*10],ta[257*4],tb[257*4];
    VslParams p=vsl_default_params(0);unsigned block,i,changed=0;int c;
    assert(a&&b);vsl_init(a,48000,48271);vsl_init(b,48000,48271);
    assert(vsl_envelope_init(&sa,48000,0)&&vsl_envelope_init(&sb,48000,mode));
    p.rpm=6500;p.load=.85;p.pressure_texture=.65;p.structure_transfer=.65;
    for(block=0;block<450;++block) {
        if(block==180)p.load=-.8;
        if(block==330)p.load=.8;
        vsl_set_params(a,&p);vsl_set_params(b,&p);
        assert(vsl_envelope_process_layout(a,&sa,aa,257,channels,oa,ta));
        assert(vsl_envelope_process_layout(b,&sb,bb,257,channels,ob,tb));
        assert(!memcmp(&a->drive,&b->drive,sizeof a->drive));
        assert(!memcmp(&a->excitation,&b->excitation,sizeof a->excitation));
        assert(!memcmp(&a->combustion,&b->combustion,sizeof a->combustion));
        assert(!memcmp(&a->character,&b->character,sizeof a->character));
        assert(!memcmp(&a->dna,&b->dna,sizeof a->dna));
        assert(!memcmp(&a->high_orders,&b->high_orders,sizeof a->high_orders));
        if(!mode)assert(!memcmp(aa,bb,257*channels*sizeof(float)));
        for(i=0;i<257;++i) {
            for(c=0;c<2;++c) {
                double delta=(ob[i*10+c]-oa[i*10+c])-(tb[i*4+c+2]-ta[i*4+c+2]);
                assert(ta[i*4+c]==tb[i*4+c]&&fabs(delta)<3e-7);
            }
            for(c=0;c<10;++c) {
                assert(isfinite(ob[i*10+c]));
                if(c!=VSL_EXHAUST_L&&c!=VSL_EXHAUST_R&&c!=VSL_BODY)assert(oa[i*10+c]==ob[i*10+c]);
                if(oa[i*10+c]!=ob[i*10+c])++changed;
            }
        }
    }
    assert(mode?changed>1000:changed==0);free(a);free(b);
}
static void native_bypass(void) {
    VslEngine *a=malloc(sizeof *a),*b=malloc(sizeof *b);VslEnvelopeTransfer s;
    float aa[257*2],bb[257*2],oa[257*10],ob[257*10];VslParams p=vsl_default_params(0);unsigned i;
    assert(a&&b);vsl_init(a,48000,48271);vsl_init(b,48000,48271);assert(vsl_envelope_init(&s,48000,0));
    p.rpm=8000;p.load=.85;vsl_set_params(a,&p);vsl_set_params(b,&p);
    for(i=0;i<200;++i) {
        assert(vsl_process_layout(a,aa,257,2,oa));assert(vsl_envelope_process_layout(b,&s,bb,257,2,ob,NULL));
        assert(!memcmp(aa,bb,sizeof aa)&&!memcmp(oa,ob,sizeof oa));
        assert(!memcmp(&a->drive,&b->drive,sizeof a->drive));
    }
    free(a);free(b);
}
static void layouts_and_blocks(void) {
    VslEngine *a=malloc(sizeof *a),*b=malloc(sizeof *b);VslEnvelopeTransfer sa,sb;
    float aa[257*2],bb[257*12],oa[257*10],ob[257*10],ta[257*4],tb[257*4];
    VslParams p=vsl_default_params(0);unsigned i,j;
    assert(a&&b);vsl_init(a,48000,48271);vsl_init(b,48000,48271);
    assert(vsl_envelope_init(&sa,48000,2)&&vsl_envelope_init(&sb,48000,2));
    p.rpm=8000;p.load=.85;vsl_set_params(a,&p);vsl_set_params(b,&p);
    for(i=0;i<100;++i) {
        assert(vsl_envelope_process_layout(a,&sa,aa,257,2,oa,ta));
        for(j=0;j<257;++j)assert(vsl_envelope_process_layout(b,&sb,bb+j*12,1,12,ob+j*10,tb+j*4));
        assert(!memcmp(oa,ob,sizeof oa)&&!memcmp(ta,tb,sizeof ta));
        assert(!memcmp(&sa,&sb,sizeof sa));
    }
    free(a);free(b);
}
static void eligibility(void) {
    VslEngine *e=malloc(sizeof *e);VslEnvelopeTransfer s;int variant;
    assert(e);vsl_init(e,48000,48271);assert(vsl_envelope_init(&s,48000,2));
    for(variant=0;variant<3;++variant) {
        e->smooth.profile=VSL_V10;e->dna.custom_count=0;e->target.pure_osc=0;vsl_envelope_prepare(&s,e);
        (void)vsl_envelope_side_tick(&s,0,1);
        e->smooth.profile=variant==0?VSL_V8:VSL_V10;e->dna.custom_count=variant==1;e->target.pure_osc=variant==2;
        vsl_envelope_prepare(&s,e);assert(vsl_envelope_side_tick(&s,0,.123)==.123);
        e->smooth.profile=VSL_V10;e->dna.custom_count=0;e->target.pure_osc=0;vsl_envelope_prepare(&s,e);
        assert(vsl_envelope_side_tick(&s,0,0)==0);
    }
    free(e);
}
int main(void) {
    int mode;filters();native_bypass();for(mode=0;mode<3;++mode) { integration(mode,2);integration(mode,12); }
    layouts_and_blocks();eligibility();puts("fired envelope: native bypass, stable/DC/tail, independent fuel/events/extra sources, block/layout and eligibility pass");return 0;
}
