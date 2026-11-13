#include "models.h"
#include "atlas_take/player.h"
#include "atlas_take/parameters.h"
#include "atlas_take_io/file.h"
#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#define CHECK(x) do{if(!(x)){fprintf(stderr,"recipe drive line%d: %s\n",__LINE__,#x);return 1;}}while(0)
#define FRAMES 96000
static FrModels models;
static AmRender a,b;
static VslEngine ea,eb;
static AtPlayer player;
static float reference[FRAMES*2],replay[FRAMES*2],wide[512*12];
static float raw[1024],dna[1024],residual[1024],body[1024],events[512],aux[512*VSL_OBJECTS];
static float start[1024],catching[1024],detail[1024],lowraw[1024],low[1024],observed[1024],bed[512*12];
static AdTelemetry telemetry[512];
static AdConfig configuration(void) {
    AdConfig c={0};c.bank=&models.bank;c.seed=48271;c.profile=VSL_V10;c.channels=2;
    c.root_per_rpm=1./120;c.scene_mode=AD_SCENE_STEREO_BED;
    c.resonant_bank=&models.resonance;c.recipe_bank=&models.recipe;return c;
}
static AdControl control(void) {
    AdControl c={0};c.drive.mode=VSL_BENCH;c.drive.ignition=1;c.drive.start_id=1;c.drive.gear=1;
    c.drive.rpm=models.dna.base_hz*120;c.drive.load=.7;
    c.mix.gain=.25;c.mix.detail=1;c.mix.width=1;return c;
}
static AdCapture capture(void) {
    AdCapture c={0};c.dna_raw=raw;c.dna=dna;c.residual=residual;c.body=body;c.events=events;
    c.aux_objects=aux;c.startup=start;c.catch_bloom=catching;c.resonant=detail;
    c.coherent_low_raw=lowraw;c.coherent_low=low;c.observation=observed;c.bed=bed;c.telemetry=telemetry;return c;
}
static int bypass_and_support(void) {
    AdConfig cfg=configuration();AdControl c=control(),bad=c;AdCapture cap=capture();unsigned at,n;
    cfg.recipe_bank=NULL;CHECK(am_render_init(&a,&ea,&cfg,&c));
    cfg.recipe_bank=&models.recipe;CHECK(am_render_init(&b,&eb,&cfg,&c));
    CHECK(am_render_process(&a,reference,30000,0,NULL)&&am_render_process(&b,replay,30000,0,NULL));
    CHECK(!memcmp(reference,replay,30000*2*sizeof(float))&&a.drive.dna.phase==b.drive.dna.phase);
    CHECK(b.drive.recipe.frame==30000&&!memcmp(&ea.drive,&eb.drive,sizeof ea.drive));
    bad.mix.coherent_low_gain=NAN;CHECK(!ad_render_set(&b.drive,&bad));
    bad=c;bad.mix.coherent_low_gain=1;CHECK(!ad_render_set(&a.drive,&bad));
    CHECK(!am_render_init(&a,&ea,&(AdConfig){0},&c));
    /* Independent state clone predicts unmodified DNA outside local support.
       This catches leftover withdrawal after the detail/LF have faded out. */
    c.mix.resonant_gain=c.mix.coherent_low_gain=1;c.drive.rpm=8000;
    CHECK(am_render_init(&b,&eb,&cfg,&c));
    for(at=0;at<24000;at+=n) {
        SaVoice before=b.drive.dna;
        n=24000-at;if(n>240)n=240;
        CHECK(am_render_process(&b,replay,n,0,&cap));
        /* All samples at zero or at the far unsupported end have unity shape.
           Driver changes are intentionally consumed by the original render. */
        if(at>=18000) {
            before.root_target=b.drive.dna.root_target;before.detail_target=b.drive.dna.detail_target;
            for(unsigned j=0;j<n;++j) {
                double x[2];sa_voice_tick(&before,x);
                CHECK(telemetry[j].resonant_support==0&&telemetry[j].coherent_low_support==0);
                CHECK(low[2*j]==0&&low[2*j+1]==0&&detail[2*j]==0&&detail[2*j+1]==0);
                CHECK(raw[2*j]==(float)x[0]&&raw[2*j+1]==(float)x[1]);
            }
        }
    }
    puts("PASS: null/zero output and controller exact; unsupported detail restores original DNA");return 0;
}
static void rehash(unsigned char *p,size_t n) {
    uint64_t h=AT_HASH_INITIAL;
    for(size_t i=0;i<n-8;++i){h^=p[i];h*=UINT64_C(1099511628211);}
    for(unsigned i=0;i<8;++i)p[n-8+i]=(unsigned char)(h>>(8*i));
}
static int take_and_routing(void) {
    AdConfig cfg=configuration();AdControl c=control();AdCapture cap=capture();AtTake t={0},loaded={0};
    unsigned at,n,count;uint64_t sh=AT_HASH_INITIAL,ah=AT_HASH_INITIAL;double lp=0,dp=0;
    unsigned char *bytes=NULL,*again=NULL;size_t length=0,length2=0;
    c.mix.resonant_gain=c.mix.coherent_low_gain=1;
    CHECK(at_take_allocate(&t,32)&&at_take_begin(&t,&cfg,&c)&&at_take_event(&t,0,&c));
    CHECK(am_render_init(&a,&ea,&t.assets->config,&c));
    for(at=0;at<FRAMES;at+=n) {
        n=FRAMES-at;if(n>257)n=257;
        for(unsigned boundary=12000;boundary<=72000;boundary+=12000)if(at<boundary&&at+n>boundary)n=boundary-at;
        if(at==12000){c.mix.coherent_low_gain=0;CHECK(at_take_event(&t,at,&c)&&am_render_set(&a,&c));}
        if(at==24000){c.mix.resonant_gain=0;CHECK(at_take_event(&t,at,&c)&&am_render_set(&a,&c));}
        if(at==36000){c.drive.rpm=8000;CHECK(at_take_event(&t,at,&c)&&am_render_set(&a,&c));}
        if(at==48000){c.mix.resonant_gain=.5;c.mix.coherent_low_gain=.6;CHECK(at_take_event(&t,at,&c)&&am_render_set(&a,&c));}
        if(at==60000){c.drive.rpm=models.dna.base_hz*120;CHECK(at_take_event(&t,at,&c)&&am_render_set(&a,&c));}
        if(at==72000){c.mix.resonant_gain=c.mix.coherent_low_gain=1;CHECK(at_take_event(&t,at,&c)&&am_render_set(&a,&c));}
        CHECK(am_render_process(&a,reference+2*at,n,0,&cap));
        for(unsigned j=0;j<n;++j)for(unsigned ch=0;ch<2;++ch) {
            unsigned k=2*j+ch;double expected=(double)dna[k]+detail[k]+low[k];
            CHECK(fabs(observed[k]-expected)<8e-7&&bed[k]==observed[k]);
            CHECK(body[k]==0&&residual[k]==0&&events[j]==0);
            lp+=(double)low[k]*low[k];dp+=(double)detail[k]*detail[k];
        }
        sh=at_hash_sources(sh,&cap,n);ah=at_hash_samples(ah,reference+2*at,n*2);CHECK(at_take_commit(&t,n,ah,sh));
    }
    CHECK(lp>1e-5&&dp>1e-5);at_take_finish(&t);
    CHECK(at_fields(&count)&&count==32&&at_take_encode(&t,&bytes,&length));
    CHECK(bytes[8]==10&&bytes[76]==32&&at_take_decode(&loaded,bytes,length));
    CHECK(loaded.assets->config.recipe_bank==&loaded.assets->recipe&&loaded.assets->config.resonant_bank==&loaded.assets->resonant);
    CHECK(loaded.assets->recipe.low[0].harmonics==7&&loaded.assets->recipe.colour[0].power_reduction==.35);
    CHECK(at_take_encode(&loaded,&again,&length2)&&length==length2&&!memcmp(bytes,again,length));free(again);
    loaded.assets->recipe.reduction[0][50]+=.01;CHECK(!at_assets_valid(loaded.assets));loaded.assets->recipe.reduction[0][50]-=.01;
    /* Restore from exact payload; invalid versions must leave destination owned. */
    CHECK(at_take_decode(&loaded,bytes,length));
    {AtAssets *saved=loaded.assets;bytes[8]=7;rehash(bytes,length);
        CHECK(!at_take_decode(&loaded,bytes,length)&&loaded.assets==saved);bytes[8]=10;rehash(bytes,length);}
    CHECK(at_take_decode(&loaded,bytes,length));
    memset(&models,0,sizeof models);at_take_free(&t);
    CHECK(at_player_init(&player,&eb,&loaded,2));
    for(at=0;at<FRAMES;at+=n){n=FRAMES-at;if(n>347)n=347;CHECK(at_player_process(&player,replay+2*at,n,NULL)==n);}
    CHECK(at_player_verified(&player)&&!memcmp(reference,replay,sizeof reference));
    CHECK(at_player_init(&player,&eb,&loaded,12));
    for(at=0;at<FRAMES;at+=n) {
        n=FRAMES-at;if(n>512)n=512;CHECK(at_player_process(&player,wide,n,NULL)==n);
        for(unsigned j=0;j<n;++j){CHECK(wide[j*12]==reference[(at+j)*2]&&wide[j*12+1]==reference[(at+j)*2+1]);
            for(unsigned ch=2;ch<12;++ch)CHECK(wide[j*12+ch]==0);}
    }
    CHECK(at_player_verified(&player)&&player.source_hash==sh);
    free(bytes);at_take_free(&loaded);
    printf("PASS: moving35 one driver, independent LF/detail controls and stems; owned schema10/32, 2/12 source/front exact; LF energy %.9g detail %.9g\n",lp,dp);
    return 0;
}
int main(void) {
    CHECK(fr_models_load(&models));CHECK(!bypass_and_support());CHECK(!take_and_routing());return 0;
}
