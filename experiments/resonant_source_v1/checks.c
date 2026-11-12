#include "resonant_source/output.h"
#include <math.h>
#include <stdio.h>
#include <string.h>
#define CHECK(x) do {if(!(x)){fprintf(stderr,"line%d: %s\n",__LINE__,#x);return 1;}}while(0)
static SdProfile original,prepared,saved;
static RdtProfile detail;
static RssVoice muted,audible,before,bypass;
static DsSource legacy;
static RssFrame a,b;
static void fixture(void) {
    unsigned h;
    memset(&original,0,sizeof original);
    original.rate=48000;original.window=1024;original.hop=256;original.base_hz=50;
    original.harmonics=64;original.components=1;original.rho[0]=.3;
    for(h=0;h<64;++h) {
        original.harmonic[h].mean[0]=.01;original.harmonic[h].mean[1]=.002;
        original.harmonic[h].mean[2]=.008;original.harmonic[h].mean[3]=-.001;
        original.harmonic[h].rho=.2;
        original.harmonic[h].basis[0][0]=.0001;
        original.harmonic[h].root[0][0]=.0002;
    }
    memset(&detail,0,sizeof detail);detail.rate=48000;detail.base_hz=50;
    detail.count=1;detail.warmup_frames=97;
    detail.band[0].low_hz=400;detail.band[0].high_hz=6000;
    detail.band[0].order=2;detail.band[0].a[0]=1;
    detail.band[0].a[1]=-.97;detail.band[0].a[2]=.97*.97;
    detail.band[0].sections=1;detail.band[0].sos[0][0]=detail.band[0].sos[0][3]=1;
    detail.band[0].sigma=.1;detail.band[0].gain=.02;detail.band[0].right_over_left=.7;
    detail.band[0].envelope_order=1;detail.band[0].beta[0]=.2;
}
int main(void) {
    RssColour colour={0,1200,1900};RssConfig cfg={0};
    RssControl ctl={{1,1,1,1,1,0},1},off;
    unsigned h,n,c;double two[2],twelve[12],phase=0,pitch=1;
    SbLayout l2,l12;DsSourceFrame old;
    fixture();CHECK(rss_profile_valid(&original));
    CHECK(rss_profile_prepare(&prepared,&original,&colour));CHECK(!memcmp(&original,&prepared,sizeof original));
    colour.power_reduction=.35;CHECK(rss_profile_prepare(&prepared,&original,&colour));
    for(h=0;h<24;++h)CHECK(!memcmp(original.harmonic+h,prepared.harmonic+h,sizeof(SdHarmonic)));
    CHECK(fabs(prepared.harmonic[30].mean[0]/.01-sqrt(1-.35*.5))<1e-15);
    CHECK(fabs(prepared.harmonic[50].mean[0]/.01-sqrt(.65))<1e-15);
    for(h=0;h<64;++h)CHECK(prepared.harmonic[h].rho==original.harmonic[h].rho);
    CHECK(!memcmp(prepared.rho,original.rho,sizeof original.rho));saved=prepared;
    colour.power_reduction=NAN;CHECK(!rss_profile_prepare(&prepared,&original,&colour));
    CHECK(!memcmp(&prepared,&saved,sizeof saved));colour.power_reduction=.35;
    CHECK(!rss_profile_prepare(&original,&original,&colour));
    original.harmonic[0].mean[0]=NAN;CHECK(!rss_profile_prepare(&prepared,&original,&colour));
    CHECK(!memcmp(&prepared,&saved,sizeof saved));original.harmonic[0].mean[0]=.01;
    cfg.source.dna=&prepared;cfg.source.dna_seed=cfg.source.low_seed=48271;cfg.source.low_scale=1;
    cfg.detail_seed=71;
    CHECK(rss_voice_init(&bypass,&cfg,&ctl));CHECK(ds_source_init(&legacy,&cfg.source,&ctl.source));
    for(n=0;n<2048;++n) {
        CHECK(rss_voice_tick(&bypass,&a));ds_source_tick(&legacy,&old);
        CHECK(!memcmp(&a.source,&old,sizeof old));
        CHECK(a.detail[0]==0&&a.detail[1]==0);
        for(c=0;c<2;++c)CHECK(a.mix[c]==old.dna[c]+old.low[c]);
    }
    cfg.detail=&detail;off=ctl;off.detail_gain=0;
    CHECK(rss_voice_init(&muted,&cfg,&off));CHECK(rss_voice_init(&audible,&cfg,&ctl));
    CHECK(muted.source.frame==0&&muted.detail.frame==97);
    CHECK(muted.source.dna.oscillator.phase==0);
    CHECK(sb_layout_init(&l2,2)&&sb_layout_init(&l12,12));
    for(n=0;n<4096;++n) {
        if(n==1000||n==2100) {
            ctl.source.pitch=off.source.pitch=n==1000?.9:1.1;
            CHECK(rss_voice_set(&muted,&off)&&rss_voice_set(&audible,&ctl));
        }
        CHECK(rss_voice_tick(&muted,&a)&&rss_voice_tick(&audible,&b));
        CHECK(!memcmp(&a.source,&b.source,sizeof a.source));
        CHECK(!memcmp(a.detail_raw,b.detail_raw,sizeof a.detail_raw));
        CHECK(!memcmp(&muted.detail,&audible.detail,sizeof muted.detail));
        CHECK(a.detail[0]==0&&a.detail[1]==0);
        CHECK(fabs(b.phase_cycles-phase/(2*3.14159265358979323846))<1e-13);
        pitch+=(1-exp(-1/(.018*48000)))*(ctl.source.pitch-pitch);
        phase+=2*3.14159265358979323846*pitch*50/48000;
        if(phase>=2*3.14159265358979323846)phase-=2*3.14159265358979323846;
        CHECK(rss_output_frame(&l2,&b,.5,1,two));CHECK(rss_output_frame(&l12,&b,.5,1,twelve));
        CHECK(!memcmp(two,twelve,sizeof two));
        for(c=2;c<12;++c)CHECK(twelve[c]==0);
    }
    CHECK(audible.source.frame==4096&&audible.detail.frame==4096+97);
    before=audible;ctl.detail_gain=NAN;CHECK(!rss_voice_set(&audible,&ctl));
    CHECK(!memcmp(&before,&audible,sizeof before));ctl.detail_gain=1;
    ctl.source.phase_texture=1;CHECK(!rss_voice_set(&audible,&ctl));ctl.source.phase_texture=0;
    detail.base_hz=51;CHECK(!rss_voice_init(&audible,&cfg,&ctl));
    CHECK(!memcmp(&before,&audible,sizeof before));detail.base_hz=50;
    ctl.source.dna_gain=0;CHECK(rss_voice_set(&audible,&ctl));
    for(n=0;n<4800;++n)CHECK(rss_voice_tick(&audible,&b));
    CHECK(audible.source.dna_gain<.004);
    for(c=0;c<2;++c)CHECK(fabs(b.detail[c])<=.004*fabs(b.detail_raw[c]));
    two[0]=12;two[1]=34;CHECK(!rss_output_frame(&l2,&b,NAN,1,two));CHECK(two[0]==12&&two[1]==34);
    puts("resonant source: recipe, bypass, transactional rejection, one phase, silent clocks, fuel envelope,2/12 routing pass");
    return 0;
}
