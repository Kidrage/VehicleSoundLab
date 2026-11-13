#define _CRT_SECURE_NO_WARNINGS
#include "modal_texture/voice.h"
#include "modal_texture/io.h"
#include <math.h>
#include <stdio.h>
#include <string.h>
#define CHECK(x) do{if(!(x)){fprintf(stderr,"line%u: %s\n",(unsigned)__LINE__,#x);return 1;}}while(0)
static MsProfile source(void) {
    MsProfile p;memset(&p,0,sizeof p);p.rate=MS_RATE;p.count=2;
    p.mode[0].hz=83.17;p.mode[0].amplitude[0]=.2;p.mode[0].amplitude[1]=.1;
    p.mode[0].phase[0]=.1;p.mode[0].phase[1]=.3;
    p.mode[1].hz=193.41;p.mode[1].amplitude[0]=.03;p.mode[1].amplitude[1]=.04;
    p.mode[1].phase[0]=.2;p.mode[1].phase[1]=-.1;return p;
}
static MtProfile profile(void) {
    MtProfile p;memset(&p,0,sizeof p);p.rate=MT_RATE;p.count=2;p.hop_frames=97;p.alpha=.7;
    p.factor[0][0]=.1;p.factor[1][0]=.04;p.factor[1][1]=.07;return p;
}
static int controls(void) {
    MtProfile p=profile(),bad;MsProfile m=source();MtVoice v,before;
    MtEnvelope e,saved,a,b;double gain[MT_MAX_MODES],other[MT_MAX_MODES];unsigned n,i;
    CHECK(mt_profile_valid(&p));CHECK(mt_voice_init(&v,&m,&p,149921,1,1,.5));before=v;
    CHECK(!mt_voice_set(&v,1,1,NAN)&&!memcmp(&v,&before,sizeof v));
    CHECK(!mt_voice_set(&v,4.1,1,0)&&!memcmp(&v,&before,sizeof v));
    CHECK(!mt_voice_tick(&v,NULL)&&!memcmp(&v,&before,sizeof v));
    bad=p;bad.factor[0][1]=INFINITY;CHECK(!mt_voice_init(&v,&m,&bad,1,1,1,0)&&!memcmp(&v,&before,sizeof v));
    bad=p;bad.factor[0][0]=.26;CHECK(!mt_profile_valid(&bad));
    bad=p;bad.count=1;CHECK(!mt_voice_init(&v,&m,&bad,1,1,1,0));
    bad=p;bad.hop_frames=0;CHECK(!mt_profile_valid(&bad));
    bad=p;bad.alpha=.981;CHECK(!mt_profile_valid(&bad));
    CHECK(mt_envelope_init(&e,&p,149921,0));saved=e;
    CHECK(!mt_envelope_set(&e,-.01)&&!memcmp(&e,&saved,sizeof e));
    CHECK(mt_envelope_set(&e,1));
    for(n=0;n<MT_RAMP_FRAMES;++n) {
        double previous=e.amount;unsigned remaining=e.remaining;
        CHECK(mt_envelope_set(&e,1)&&e.remaining==remaining);
        CHECK(mt_envelope_tick(&e,gain)&&e.amount>=previous&&e.amount<=1);
    }
    CHECK(e.amount==1&&e.remaining==0);CHECK(mt_envelope_set(&e,0));
    for(n=0;n<MT_RAMP_FRAMES;++n){double previous=e.amount;CHECK(mt_envelope_tick(&e,gain)&&e.amount<=previous&&e.amount>=0);}
    CHECK(e.amount==0&&!e.remaining);
    /* Zero amount still consumes precisely the same state and RNG sequence. */
    CHECK(mt_envelope_init(&a,&p,277139,0)&&mt_envelope_init(&b,&p,277139,1));
    for(n=0;n<20001;++n) {
        CHECK(mt_envelope_tick(&a,gain)&&mt_envelope_tick(&b,other));
        for(i=0;i<p.count;++i)CHECK(gain[i]==1&&isfinite(other[i])&&other[i]>0);
    }
    CHECK(a.rng==b.rng&&a.has_spare==b.has_spare&&a.spare==b.spare&&a.position==b.position);
    CHECK(!memcmp(a.left,b.left,sizeof a.left)&&!memcmp(a.right,b.right,sizeof a.right));
    memset(p.factor,0,sizeof p.factor);CHECK(mt_envelope_init(&e,&p,1,1));
    for(n=0;n<2001;++n){CHECK(mt_envelope_tick(&e,gain));for(i=0;i<p.count;++i)CHECK(gain[i]==1);}
    /* Singular, nonzero covariance is legal; duplicated rows share gains. */
    p.factor[0][0]=p.factor[1][0]=.12;CHECK(mt_envelope_init(&e,&p,1,1));
    for(n=0;n<2001;++n){CHECK(mt_envelope_tick(&e,gain));CHECK(gain[0]==gain[1]);}
    return 0;
}
static int source_compatibility(void) {
    MsProfile p=source();MtProfile model=profile();MsVoice old,nullable,unity,saved;MtVoice adapted;
    unsigned n;double a[2],b[2],g[2]={1,1};
    CHECK(ms_voice_init(&old,&p,1,1));nullable=unity=old;
    CHECK(mt_voice_init(&adapted,&p,&model,149921,1,1,0));
    for(n=0;n<100003;++n) {
        if(n==731||n==17771) {
            double r=n==731?1.1:.9,gain=n==731?0:1;
            CHECK(ms_voice_set(&old,r,gain)&&ms_voice_set(&nullable,r,gain)&&ms_voice_set(&unity,r,gain));
            CHECK(mt_voice_set(&adapted,r,gain,0));
        }
        CHECK(ms_voice_tick(&old,a)&&ms_voice_tick_gains(&nullable,NULL,b)&&!memcmp(a,b,sizeof a));
        CHECK(ms_voice_tick_gains(&unity,g,b)&&!memcmp(a,b,sizeof a));
        CHECK(mt_voice_tick(&adapted,b)&&!memcmp(a,b,sizeof a));
        CHECK(!memcmp(&old,&nullable,sizeof old)&&!memcmp(&old,&unity,sizeof old)&&!memcmp(&old,&adapted.source,sizeof old));
    }
    saved=old;g[1]=NAN;CHECK(!ms_voice_tick_gains(&old,g,a)&&!memcmp(&old,&saved,sizeof old));
    g[1]=-.1;CHECK(!ms_voice_tick_gains(&old,g,a)&&!memcmp(&old,&saved,sizeof old));return 0;
}
static int chunks(void) {
    MsProfile m=source();MtProfile p=profile();MtVoice a,b;unsigned start=0,part=0,n;
    static const unsigned sizes[]={1,127,480,17,1024,3};double x[2048],y[2048];
    CHECK(mt_voice_init(&a,&m,&p,381611,1,1,.5));b=a;
    while(start<30001) {
        unsigned frames=sizes[part++%6];if(frames>30001-start)frames=30001-start;
        CHECK(mt_voice_set(&a,1.1,.8,1)&&mt_voice_set(&b,1.1,.8,1));
        CHECK(mt_voice_process(&a,x,frames));
        for(n=0;n<frames;++n)CHECK(mt_voice_tick(&b,y+2*n));
        CHECK(!memcmp(x,y,frames*2*sizeof(double))&&!memcmp(&a,&b,sizeof a));start+=frames;
    }
    return 0;
}
static int input(void) {
    static const char *invalid[]={"VSL_MODAL_TEXTURE 1 48000 1 97 0.7 nan",
        "VSL_MODAL_TEXTURE 1 48000 1.0 97 0.7 .1","VSL_MODAL_TEXTURE 1 48000 1 97 0.7 .1 extra",
        "VSL_MODAL_TEXTURE 1 48000 1 97 .7","VSL_MODAL_TEXTURE 2 48000 1 97 .7 .1"};
    MtProfile p=profile(),before=p;unsigned i;FILE *f;
    for(i=0;i<sizeof invalid/sizeof *invalid;++i) {
        f=tmpfile();CHECK(f);fputs(invalid[i],f);rewind(f);
        CHECK(!mt_profile_read(f,&p)&&!memcmp(&p,&before,sizeof p));CHECK(!fclose(f));
    }
    f=tmpfile();CHECK(f);fputs("VSL_MODAL_TEXTURE 1 48000 1 97 0.7 0.1\n",f);rewind(f);
    CHECK(mt_profile_read(f,&p)&&p.count==1&&p.factor[0][0]==.1);CHECK(!fclose(f));return 0;
}
int main(void) {
    CHECK(!controls());CHECK(!source_compatibility());CHECK(!chunks());CHECK(!input());
    puts("modal_texture_contracts_passed=1");return 0;
}
