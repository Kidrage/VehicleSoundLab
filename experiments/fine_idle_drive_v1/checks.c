#include "models.h"
#include "../full_recipe_drive_v1/models.h"
#include "modal_texture/voice.h"
#include "spectral_texture/voice.h"
#include "atlas_take_io/file.h"
#include "atlas_take/player.h"
#include "atlas_take/parameters.h"
#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#define CHECK(x) do{if(!(x)){fprintf(stderr,"owned idle line%d: %s\n",__LINE__,#x);return 1;}}while(0)
#define FRAMES 384000u
static FidModels idle;
static FrModels moving;
static AmRender a,b;
static VslEngine ea,eb;

static AtPlayer player;
static float reference[FRAMES*2],candidate[FRAMES*2],wide[512*12];
static float raw[1024],dna[1024],body[1024],residual[1024],resonant[1024],lowraw[1024],low[1024];
static float aux[512*VSL_OBJECTS],events[512],startup[1024],catching[1024],idleraw[1024],idlesound[1024];
static float core[1024],detail[1024];
static AdTelemetry telemetry[512];
static AdConfig config(void) {
    AdConfig c={0};c.bank=&moving.bank;c.seed=48271;c.profile=VSL_V10;c.channels=2;c.root_per_rpm=1./120;
    c.scene_mode=AD_SCENE_STEREO_BED;c.resonant_bank=&moving.resonance;c.recipe_bank=&moving.recipe;c.fine_idle_profile=&idle.idle;return c;
}
static AdControl control(void) {
    AdControl c={0};c.drive.mode=VSL_BENCH;c.drive.ignition=1;c.drive.start_id=1;c.drive.rpm=850;
    c.mix.idle_motion=.5;c.mix.idle_detail=1;c.mix.gain=.25;c.mix.width=c.mix.detail=c.mix.resonant_gain=c.mix.coherent_low_gain=c.mix.idle_mix=1;return c;
}
static AdCapture capture(void) {
    AdCapture c={0};c.dna_raw=raw;c.dna=dna;c.body=body;c.residual=residual;c.events=events;c.aux_objects=aux;
    c.startup=startup;c.catch_bloom=catching;c.resonant=resonant;c.coherent_low_raw=lowraw;c.coherent_low=low;
    c.idle_modal=core;c.idle_detail=detail;c.idle_raw=idleraw;c.idle=idlesound;c.telemetry=telemetry;return c;
}
static void state_event(unsigned at,AdControl *p) {
    if(at==96000){p->drive.rpm=2200;p->drive.load=.6;}
    if(at==192000){p->drive.rpm=850;p->drive.load=0;}
    if(at==288000)p->drive.ignition=0;
}
static unsigned block(unsigned at,unsigned size,unsigned quantum) {
    unsigned n=FRAMES-at;if(n>size)n=size;
    unsigned next=(at/quantum+1)*quantum;if(at+n>next)n=next-at;return n;
}
static int parity(void) {
    AdConfig c=config();AdControl p=control();AdCapture cap=capture();unsigned at,n;
    p.mix.idle_mix=0;CHECK(am_render_init(&a,&ea,&c,&p));
    for(at=0;at<FRAMES;at+=n){n=block(at,257,96000);state_event(at,&p);CHECK(am_render_set(&a,&p)&&am_render_process(&a,reference+2*at,n,0,&cap));}
    c.fine_idle_profile=NULL;p=control();p.mix.idle_mix=p.mix.idle_motion=p.mix.idle_detail=0;CHECK(am_render_init(&b,&eb,&c,&p));
    for(at=0;at<FRAMES;at+=n){n=block(at,347,96000);state_event(at,&p);CHECK(am_render_set(&b,&p)&&am_render_process(&b,candidate+2*at,n,0,NULL));}
    CHECK(!memcmp(reference,candidate,sizeof reference)&&!memcmp(&ea.drive,&eb.drive,sizeof ea.drive));
    am_render_dispose(&a);am_render_dispose(&b);
    puts("PASS zero candidate amount preserves legacy output and the one controller across arbitrary audio chunks");return 0;
}
static void rehash(unsigned char *p,size_t n) {
    uint64_t h=AT_HASH_INITIAL;size_t i;unsigned k;
    for(i=0;i<n-8;++i){h^=p[i];h*=UINT64_C(1099511628211);}
    for(k=0;k<8;++k)p[n-8+k]=(unsigned char)(h>>(8*k));
}
static int owned(void) {
    AdConfig cfg=config();AdControl p=control(),bad=p;AdCapture cap=capture();AtTake t={0},loaded={0};
    unsigned at,n,count;uint64_t sh=AT_HASH_INITIAL,ah=AT_HASH_INITIAL;double energy=0;
    unsigned char *bytes=NULL,*again=NULL;size_t length=0,length2=0;AtAssets *saved;
    CHECK(at_take_allocate(&t,64));cfg.fine_idle_profile=NULL;
    CHECK(!at_take_begin(&t,&cfg,&p)&&!am_render_init(&a,&ea,&cfg,&p));cfg.fine_idle_profile=&idle.idle;
    cfg.idle_profile=(const MlProfile*)&idle;CHECK(!at_take_begin(&t,&cfg,&p)&&!am_render_init(&a,&ea,&cfg,&p));cfg.idle_profile=NULL;
    bad.mix.idle_mix=NAN;CHECK(!ad_control_valid(&bad,2));
    CHECK(at_take_begin(&t,&cfg,&p)&&at_take_event(&t,0,&p));
    CHECK(t.assets->config.fine_idle_profile==&t.assets->fine_idle&&t.assets->fine_idle.modal==&t.assets->fine_modal&&t.assets->fine_idle.motion==&t.assets->fine_motion&&t.assets->fine_idle.detail==&t.assets->fine_detail);
    CHECK(am_render_init(&a,&ea,&t.assets->config,&p));
    for(at=0;at<FRAMES;at+=n) {
        n=block(at,257,24000);state_event(at,&p);
        if(at==24000)p.mix.idle_motion=1;
        if(at==48000)p.mix.idle_detail=.35;
        if(at==72000)p.mix.idle_mix=0;
        if(at==192000)p.mix.idle_mix=.35;
        if(at==240000){p.mix.idle_mix=1;p.mix.idle_detail=1;p.mix.idle_motion=.5;}
        if(at&&at%24000==0)CHECK(at_take_event(&t,at,&p)&&am_render_set(&a,&p));
        CHECK(am_render_process(&a,reference+2*at,n,0,&cap));
        for(unsigned j=0;j<n*2;++j)energy+=(double)idlesound[j]*idlesound[j];
        sh=at_hash_sources(sh,&cap,n);ah=at_hash_samples(ah,reference+2*at,n*2);CHECK(at_take_commit(&t,n,ah,sh));
    }
    CHECK(energy>1e-4);at_take_finish(&t);
    CHECK(at_fields(&count)&&count==32&&at_take_encode(&t,&bytes,&length));
    CHECK(bytes[8]==10&&bytes[76]==32&&at_take_decode(&loaded,bytes,length));
    CHECK(loaded.assets->fine_idle.modal==&loaded.assets->fine_modal&&loaded.assets->fine_idle.motion==&loaded.assets->fine_motion&&loaded.assets->fine_idle.detail==&loaded.assets->fine_detail);
    CHECK(loaded.assets->fine_idle.level_gain==idle.idle.level_gain&&loaded.assets->fine_idle.attack_frames==3840);
    CHECK(at_take_encode(&loaded,&again,&length2)&&length==length2&&!memcmp(bytes,again,length));free(again);
    saved=loaded.assets;bytes[8]=9;rehash(bytes,length);CHECK(!at_take_decode(&loaded,bytes,length)&&loaded.assets==saved);
    bytes[8]=10;rehash(bytes,length);CHECK(at_take_decode(&loaded,bytes,length));
    {unsigned char header[8]={0x80,0xbb,0,0,13,0,0,0};size_t found=0;unsigned matches=0;
        for(size_t j=80;j+8<length-8;++j)if(!memcmp(bytes+j,header,8)){found=j;++matches;}
        CHECK(matches==2);saved=loaded.assets;bytes[found+4]=65;rehash(bytes,length);
        CHECK(!at_take_decode(&loaded,bytes,length)&&loaded.assets==saved);
        bytes[found+4]=13;rehash(bytes,length);CHECK(at_take_decode(&loaded,bytes,length));}
    {unsigned char header[12]={0x80,0xbb,0,0,6,0,0,0,0x80,0xbb,0,0};size_t found=0;unsigned matches=0;
        for(size_t j=80;j+12<length-8;++j)if(!memcmp(bytes+j,header,12)){found=j+12;++matches;}
        CHECK(matches==1&&bytes[found]==0&&bytes[found+1]==32);saved=loaded.assets;
        bytes[found]=1;rehash(bytes,length);CHECK(!at_take_decode(&loaded,bytes,length)&&loaded.assets==saved);
        bytes[found]=0;rehash(bytes,length);CHECK(at_take_decode(&loaded,bytes,length));
        saved=loaded.assets;CHECK(!at_take_decode(&loaded,bytes,length-1)&&loaded.assets==saved);}
    {double value=loaded.assets->fine_idle.modal_ratio;loaded.assets->fine_idle.modal_ratio=NAN;CHECK(!at_assets_valid(loaded.assets));loaded.assets->fine_idle.modal_ratio=value;}
    {unsigned taps=loaded.assets->fine_detail.band[0].count;loaded.assets->fine_detail.band[0].count=PF_MAX_TAPS+1;CHECK(!at_assets_valid(loaded.assets));loaded.assets->fine_detail.band[0].count=taps;}
    am_render_dispose(&a);memset(&idle,0,sizeof idle);memset(&moving,0,sizeof moving);at_take_free(&t);
    CHECK(at_player_init(&player,&eb,&loaded,2));
    for(at=0;at<FRAMES;at+=n){n=FRAMES-at;if(n>349)n=349;CHECK(at_player_process(&player,candidate+2*at,n,NULL)==n);}
    CHECK(at_player_verified(&player)&&!memcmp(reference,candidate,sizeof reference));
    at_player_dispose(&player);CHECK(at_player_init(&player,&eb,&loaded,12));
    for(at=0;at<FRAMES;at+=n) {
        n=FRAMES-at;if(n>512)n=512;CHECK(at_player_process(&player,wide,n,NULL)==n);
        for(unsigned j=0;j<n;++j){CHECK(wide[j*12]==reference[2*(at+j)]&&wide[j*12+1]==reference[2*(at+j)+1]);
            for(unsigned ch=2;ch<12;++ch)CHECK(wide[j*12+ch]==0);}
    }
    CHECK(at_player_verified(&player)&&player.source_hash==sh);
    at_player_dispose(&player);free(bytes);at_take_free(&loaded);puts("PASS owned schema10/32, amount events, external source destruction, corrupt/invalid transaction, arbitrary chunks and2/12source exact");return 0;
}
int main(void){CHECK(fid_models_load(&idle)&&fr_models_load(&moving));CHECK(!parity());CHECK(!owned());return 0;}
