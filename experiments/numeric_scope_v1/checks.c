#include "rt_numeric/scope.h"
#include "atlas_take/player.h"
#include <float.h>
#include <math.h>
#include <stdio.h>
#include <string.h>
#if defined(_M_X64) || defined(__x86_64__)
#include <xmmintrin.h>
#define HAS_MXCSR 1
#else
#define HAS_MXCSR 0
#endif
#define CHECK(x) do{if(!(x)){fprintf(stderr,"numeric check line%d: %s\n",__LINE__,#x);return 0;}}while(0)
#define FRAMES 12000
static SdProfile profile;static SaBank bank;
static AmRender voices[2];static VslEngine engines[3];static AtPlayer player;
static float audio[2][FRAMES*2],raw[512*2],dna[512*2],body[512*2],events[512];
static float residual[512*2],auxiliary[512*VSL_OBJECTS];
static unsigned original;
static unsigned get_flags(void) {
#if HAS_MXCSR
    return _mm_getcsr();
#else
    return 0;
#endif
}
static void set_flags(unsigned value) {
#if HAS_MXCSR
    _mm_setcsr(value);
#else
    (void)value;
#endif
}
static unsigned caller(int flush) {return ((original|0x1f80u)&~0xe040u)|(flush?0x8040u:0);}
static int boundaries(void) {
    unsigned rounding,flush;
    CHECK(rn_scope_available()==HAS_MXCSR);
    for(rounding=0;rounding<4;++rounding)for(flush=0;flush<4;++flush) {
        unsigned incoming=caller(0)|(rounding<<13)|((flush&1)?0x8000u:0)|((flush&2)?0x40u:0)|0x21u;
        RnScope outer,inner;unsigned entered;
        set_flags(incoming);incoming=get_flags();outer=rn_scope_enter();entered=get_flags();
        CHECK(entered==(HAS_MXCSR?(incoming|0x8040u):incoming));
        inner=rn_scope_enter();CHECK(get_flags()==entered);rn_scope_leave(inner);CHECK(get_flags()==entered);
        rn_scope_leave(outer);CHECK(get_flags()==incoming);
        CHECK(!ad_render_process(NULL,NULL,1,NULL)&&get_flags()==incoming);
        CHECK(!am_render_process(NULL,NULL,1,0,NULL)&&get_flags()==incoming);
    }
#if HAS_MXCSR
    {
        volatile float small=FLT_MIN,half=.5f,tiny;float value;unsigned bits;
        RnScope scope;
        set_flags(caller(0));value=small*half;memcpy(&bits,&value,sizeof bits);CHECK(bits==0x00400000u);
        set_flags(caller(0));scope=rn_scope_enter();value=small*half;memcpy(&bits,&value,sizeof bits);CHECK(bits==0);
        rn_scope_leave(scope);CHECK(get_flags()==caller(0));
        bits=1;memcpy((void*)&tiny,&bits,sizeof bits);
        set_flags(caller(0));value=tiny+tiny;memcpy(&bits,&value,sizeof bits);CHECK(bits==2);
        set_flags(caller(0));scope=rn_scope_enter();value=tiny+tiny;memcpy(&bits,&value,sizeof bits);CHECK(bits==0);
        rn_scope_leave(scope);CHECK(get_flags()==caller(0));
    }
#endif
    return 1;
}
static int fixture(AdConfig *config,AdControl *control) {
    const SdProfile *p=&profile;unsigned h;
    memset(&profile,0,sizeof profile);memset(control,0,sizeof *control);
    profile.rate=48000;profile.window=1024;profile.hop=256;profile.base_hz=40;
    profile.harmonics=24;profile.components=1;profile.rho[0]=.4;
    for(h=0;h<24;++h) {
        SdHarmonic *z=profile.harmonic+h;z->rho=.5;
        z->mean[0]=.03/(h+1);z->mean[2]=.025*cos(.3*h)/(h+1);z->mean[3]=.025*sin(.3*h)/(h+1);
        z->basis[0][0]=.0001;z->root[2][2]=.00001;
    }
    CHECK(sa_bank_init(&bank,&p,1,0));
    *config=(AdConfig){&bank,48271,VSL_V10,2,1./120,DS_OBSERVE_MID,DS_ROUTE_PAIR,NULL};
    control->drive=(AdInput){VSL_BENCH,1,1,1,0,1,4800,.8,0,0};
    control->mix.gain=.2;control->mix.detail=1;control->mix.width=.7;control->mix.room=.2;
    control->mix.spatial=1;control->mix.propagation=1;control->mix.body_mix=.6;control->mix.event_gain=.2;
    control->mix.intake_gain=control->mix.mechanical_gain=control->mix.air_gain=.4;
    control->mix.road_gain=control->mix.wind_gain=.4;return 1;
}
static int chunking(void) {
    AdConfig config;AdControl c;unsigned run,at;
    set_flags(caller(0));CHECK(fixture(&config,&c));
    for(run=0;run<2;++run) {
        set_flags(caller(0));CHECK(am_render_init(voices+run,engines+run,&config,&c));
        for(at=0;at<FRAMES;) {
            unsigned n=run?1+(at*17)%113:512,flags=caller((int)(run^(at&1)));
            if(n>FRAMES-at)n=FRAMES-at;
            if(at<10000&&at+n>10000)n=10000-at;
            set_flags(flags);
            CHECK(am_render_process(voices+run,audio[run]+2*at,n,at>=10000,NULL));
            CHECK(get_flags()==flags);at+=n;
        }
    }
    CHECK(!memcmp(audio[0],audio[1],sizeof audio[0]));
    CHECK(!memcmp(voices[0].drive.dna.texture,voices[1].drive.dna.texture,sizeof voices[0].drive.dna.texture));
    set_flags(caller(0));voices[0].drive.body_band.stop_low=NAN;
    CHECK(!ad_render_process(&voices[0].drive,audio[0],1,NULL)&&get_flags()==caller(0));
    CHECK(!am_render_process(voices,audio[0],1,0,NULL)&&get_flags()==caller(0));return 1;
}
static int recording(void) {
    AtTake take={0};AdConfig config;AdControl c;AdCapture capture={0};unsigned at;
    uint64_t output_hash=AT_HASH_INITIAL,source_hash=AT_HASH_INITIAL;
    set_flags(caller(0));CHECK(fixture(&config,&c));
    CHECK(at_take_allocate(&take,4)&&at_take_begin(&take,&config,&c));
    CHECK(at_take_event(&take,0,&c));
    CHECK(am_render_init(voices,engines,&take.assets->config,&c));
    capture.dna_raw=raw;capture.dna=dna;capture.body=body;capture.events=events;
    capture.residual=residual;capture.aux_objects=auxiliary;
    for(at=0;at<FRAMES;) {
        unsigned n=257,flags=caller((int)(at&1));
        if(n>FRAMES-at)n=FRAMES-at;
        if(at<4096&&at+n>4096)n=4096-at;
        if(at<10000&&at+n>10000)n=10000-at;
        if(at==4096) {c.drive.rpm=6500;c.mix.spatial=0;CHECK(at_take_event(&take,at,&c)&&am_render_set(voices,&c));}
        if(at==10000)take.stop_frame=at;
        set_flags(flags);CHECK(am_render_process(voices,audio[0]+2*at,n,at>=10000,&capture));
        CHECK(get_flags()==flags);
        output_hash=at_hash_samples(output_hash,audio[0]+2*at,n*2);
        source_hash=at_hash_sources(source_hash,&capture,n);CHECK(at_take_commit(&take,n,output_hash,source_hash));at+=n;
    }
    at_take_finish(&take);set_flags(caller(0));CHECK(at_player_init(&player,engines+2,&take,2));
    for(at=0;at<FRAMES;) {
        unsigned n=1+(at*13)%511,flags=caller((int)!(at&1));if(n>FRAMES-at)n=FRAMES-at;
        set_flags(flags);CHECK(at_player_process(&player,audio[1]+2*at,n,NULL)==n&&get_flags()==flags);at+=n;
    }
    CHECK(at_player_verified(&player)&&!memcmp(audio[0],audio[1],sizeof audio[0]));
    at_take_free(&take);return 1;
}
int main(void) {
    int ok;original=get_flags();ok=boundaries()&&chunking()&&recording();set_flags(original);
    if(ok)printf("PASS: numeric scope supported%d; nested/status/rounding/error restoration, FTZ/DAZ arithmetic, chunk and varying-caller record/replay exact\n",rn_scope_available());
    return ok?0:1;
}
