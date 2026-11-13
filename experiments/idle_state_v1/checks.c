#include "source.h"
#include "../full_recipe_drive_v1/models.h"
#include "atlas_take/take.h"
#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#define CHECK(x) do{if(!(x)){fprintf(stderr,"idle integration line%d: %s\n",__LINE__,#x);return 1;}}while(0)
#define FRAMES 384000
static MiModels idle;
static FrModels moving;
static IsSource sa,sb;
static AdRender a,b;
static VslEngine ea,eb;
static float reference[FRAMES*2],candidate[FRAMES*2],wide[512*12];
static float added[1024],observation[1024],dna[1024],body[1024],residual[1024],resonance[1024],low[1024],bed[512*12];
static AdTelemetry telemetry[512];
static AdConfig config(void) {
    AdConfig c={0};c.bank=&moving.bank;c.seed=48271;c.profile=VSL_V10;c.channels=2;
    c.root_per_rpm=1./120;c.scene_mode=AD_SCENE_STEREO_BED;c.resonant_bank=&moving.resonance;c.recipe_bank=&moving.recipe;return c;
}
static AdControl control(void) {
    AdControl p={0};p.drive.mode=VSL_BENCH;p.drive.ignition=1;p.drive.start_id=1;p.drive.rpm=850;
    p.mix.gain=.25;p.mix.detail=p.mix.width=p.mix.resonant_gain=p.mix.coherent_low_gain=1;return p;
}
static AdCapture capture(void) {
    AdCapture c={0};c.source_added=added;c.observation=observation;c.bed=bed;c.telemetry=telemetry;
    c.dna=dna;c.body=body;c.residual=residual;c.resonant=resonance;c.coherent_low=low;return c;
}
static int invalid(void *s,const AdSourceContext *c,AdSourceFrame *f){(void)s;(void)c;f->stereo[AD_SOURCE_ADDED][0]=NAN;return 1;}
static int boundaries(void) {
    AdConfig cfg=config();AdControl p=control();AdCapture cap=capture();unsigned at,n;
    AdSourceProcessor bad={&idle,invalid},missing={&idle,NULL};AdSourceFrame frame={0},before=frame;
    AdSourceContext context={&ea.drive,1,1,0};AtTake take={0};AtAssets *assets;
    CHECK(!ad_source_valid(&missing)&&!ad_source_apply(&bad,&context,&frame)&&!memcmp(&frame,&before,sizeof frame));
    cfg.source_processor=&missing;CHECK(!ad_render_init(&a,&ea,&cfg,&p));cfg.source_processor=NULL;
    CHECK(ad_render_init(&a,&ea,&cfg,&p));CHECK(is_source_init(&sb,&idle,149921,0));
    cfg.source_processor=&sb.processor;CHECK(ad_render_init(&b,&eb,&cfg,&p));
    for(at=0;at<48000;at+=n) {
        n=48000-at;if(n>257)n=257;
        CHECK(ad_render_process(&a,reference+2*at,n,NULL)&&ad_render_process(&b,candidate+2*at,n,&cap));
        for(unsigned j=0;j<n*2;++j)CHECK(added[j]==0);
    }
    CHECK(!memcmp(reference,candidate,48000*2*sizeof(float))&&sb.voice.frame==48000);
    CHECK(!memcmp(&ea.drive,&eb.drive,sizeof ea.drive)&&a.dna.phase==b.dna.phase);
    CHECK(at_take_allocate(&take,8));cfg.source_processor=NULL;
    CHECK(at_take_begin(&take,&cfg,&p));assets=take.assets;cfg.source_processor=&sb.processor;
    CHECK(!at_take_begin(&take,&cfg,&p)&&take.assets==assets);at_take_free(&take);
    puts("PASS null/disabled exact bypass, controller unchanged, finite callback boundary, unsupported take transaction");return 0;
}
static unsigned event(unsigned frame,AdControl *p) {
    if(frame==96000){p->drive.rpm=2200;p->drive.load=.6;return 1;}
    if(frame==192000){p->drive.rpm=850;p->drive.load=0;return 1;}
    if(frame==288000){p->drive.ignition=0;return 1;}
    return 0;
}
static int driving(void) {
    AdConfig cfg=config();AdControl p=control();AdCapture cap=capture();unsigned at,n,idle_full=0,other_zero=0;
    double energy=0,maximum_slope=0,previous=0;
    CHECK(is_source_init(&sa,&idle,149921,1));cfg.source_processor=&sa.processor;
    CHECK(ad_render_init(&a,&ea,&cfg,&p));
    for(at=0;at<FRAMES;at+=n) {
        n=FRAMES-at;if(n>257)n=257;
        for(unsigned boundary=96000;boundary<=288000;boundary+=96000)if(at<boundary&&at+n>boundary)n=boundary-at;
        if(event(at,&p))CHECK(ad_render_set(&a,&p));
        CHECK(ad_render_process(&a,candidate+2*at,n,&cap));
        for(unsigned j=0;j<n;++j)for(unsigned ch=0;ch<2;++ch) {
            unsigned k=2*j+ch;double expected=(double)dna[k]+body[k]+residual[k]+resonance[k]+low[k]+added[k];
            CHECK(fabs(observation[k]-expected)<2e-7&&bed[k]==observation[k]);
            CHECK(isfinite(candidate[2*(at+j)+ch]));energy+=(double)added[k]*added[k];
        }
        CHECK(sa.voice.frame==at+n&&a.frame==ea.frame&&sa.voice.frame==a.frame);
        if(sa.latest.weight==1){CHECK(sa.latest_gate);++idle_full;}
        if(sa.latest.weight==0&&!sa.latest_gate)++other_zero;
        {double slope=fabs(sa.latest.weight-previous)/n;if(slope>maximum_slope)maximum_slope=slope;previous=sa.latest.weight;}
    }
    CHECK(idle_full>20&&other_zero>20&&energy>1e-5&&sa.voice.position==0&&ea.drive.lifecycle==VSL_OFF);
    /* Same adopted controls, different block boundaries, same source and driver. */
    p=control();CHECK(is_source_init(&sb,&idle,149921,1));cfg.source_processor=&sb.processor;
    CHECK(ad_render_init(&b,&eb,&cfg,&p));
    for(at=0;at<FRAMES;at+=n) {
        n=FRAMES-at;if(n>347)n=347;
        for(unsigned boundary=96000;boundary<=288000;boundary+=96000)if(at<boundary&&at+n>boundary)n=boundary-at;
        if(event(at,&p))CHECK(ad_render_set(&b,&p));
        CHECK(ad_render_process(&b,reference+2*at,n,NULL));
    }
    CHECK(!memcmp(reference,candidate,sizeof reference)&&!memcmp(&ea.drive,&eb.drive,sizeof ea.drive));
    CHECK(!memcmp(sa.voice.modal.cosine,sb.voice.modal.cosine,sizeof sa.voice.modal.cosine)&&!memcmp(&sa.voice.detail,&sb.voice.detail,sizeof sa.voice.detail));
    printf("PASS real state schedule, per-stem accounting, arbitrary-block exact repeat; added energy %.17g; max block-average weight slope %.17g\n",energy,maximum_slope);
    /* Same render path into12channel front bed; no invented upmix or 2nd scene. */
    p=control();p.mix.spatial=1;cfg.channels=12;
    CHECK(is_source_init(&sb,&idle,149921,1));cfg.source_processor=&sb.processor;CHECK(ad_render_init(&b,&eb,&cfg,&p));
    for(at=0;at<FRAMES;at+=n) {
        n=FRAMES-at;if(n>512)n=512;
        for(unsigned boundary=96000;boundary<=288000;boundary+=96000)if(at<boundary&&at+n>boundary)n=boundary-at;
        if(event(at,&p))CHECK(ad_render_set(&b,&p));
        CHECK(ad_render_process(&b,wide,n,NULL));
        for(unsigned j=0;j<n;++j){CHECK(wide[j*12]==candidate[2*(at+j)]&&wide[j*12+1]==candidate[2*(at+j)+1]);
            for(unsigned ch=2;ch<12;++ch)CHECK(wide[j*12+ch]==0);}
    }
    CHECK(!memcmp(&ea.drive,&eb.drive,sizeof ea.drive)&&sa.enabled_samples==sb.enabled_samples);
    puts("PASS stereo/12-front exact, one controller, continuing source state");return 0;
}
int main(void) {
    CHECK(mi_models_load(&idle,"experiments/modal_idle_v1/F2_fixed_idle.msource","experiments/modal_idle_v1/F2_fixed_idle.rdetail"));
    CHECK(fr_models_load(&moving));CHECK(!boundaries());CHECK(!driving());return 0;
}
