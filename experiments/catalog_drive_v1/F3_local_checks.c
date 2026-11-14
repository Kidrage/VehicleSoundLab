#include "models.h"
#include "F3_local_models.h"
#include "atlas_drive/render.h"
#include "core/engine.h"
#include <math.h>
#include <stdio.h>
#include <string.h>
#define CHECK(x) do{if(!(x)){fprintf(stderr,"local owned%d: %s\n",__LINE__,#x);return 1;}}while(0)
static F3lModels model,before;
static SaVoice direct,compare;
static AdRender r2,r12;static VslEngine e2,e12;
static float out2[514],out12[3084],raw2[514],raw12[514],layers2[257*LM_SAMPLES],layers12[257*LM_SAMPLES];
static AdTelemetry telemetry[257];
int main(void) {
    CHECK(!f3l_models_load(NULL,0));
    for(unsigned group=0;group<2;++group) {
        int selection=DC_F3_FIRST_LOCAL+(int)group;DcPreset *p,*owned;AdConfig cfg,wide;AdControl c,uw;AdCapture a={0},b={0};
        unsigned at,n,anchors=0;double energy=0;
        CHECK(f3l_models_load(&model,group));before=model;
        CHECK(!f3l_models_load(&model,2)&&!memcmp(&model,&before,sizeof model));
        for(unsigned j=0;j<3;++j) {
            CHECK(model.bank.profile[j]==model.dna+j&&model.dna[j].harmonics==288&&model.dna[j].components==12);
            before.bank.profile[j]=before.dna+j;
        }
        p=cd_models_load(selection);CHECK(p);cfg=*dc_preset_config(p);c=dc_preset_initial(p);
        cfg.bank=&model.bank;owned=dc_preset_create(selection,&cfg,&c);CHECK(owned);
        dc_preset_destroy(p);memset(&model,0xa5,sizeof model);cfg=*dc_preset_config(owned);
        CHECK(cfg.bank!=&model.bank);
        for(unsigned j=0;j<3;++j)CHECK(!memcmp(cfg.bank->profile[j],before.dna+j,sizeof(SdProfile)));
        c.drive.ignition=c.drive.start_id=1;c.drive.gear=5;c.drive.rpm=before.dna[0].base_hz/cfg.root_per_rpm;
        wide=cfg;wide.channels=12;uw=c;uw.mix.spatial=1;
        CHECK(ad_render_init(&r2,&e2,&cfg,&c)&&ad_render_init(&r12,&e12,&wide,&uw));
        CHECK(sa_voice_init(&direct,&before.bank,cfg.seed,0,c.mix.detail,1));
        a.dna_raw=raw2;a.layers=layers2;a.telemetry=telemetry;b.dna_raw=raw12;b.layers=layers12;
        for(at=0;at<240123;at+=n) {
            n=240123-at>257?257:240123-at;
            for(unsigned j=1;j<5;++j)if(at<j*48000&&at+n>j*48000)n=j*48000-at;
            if(at==48000)c.drive.rpm=before.dna[1].base_hz/cfg.root_per_rpm;
            if(at==96000){c.drive.rpm=before.dna[2].base_hz/cfg.root_per_rpm;c.drive.load=.4;}
            if(at==144000){c.drive.rpm=before.dna[0].base_hz/cfg.root_per_rpm;c.drive.load=-.4;c.mix.detail=.6;}
            if(at==192000){c.drive.rpm=before.dna[1].base_hz/cfg.root_per_rpm;c.mix.detail=1;}
            uw=c;uw.mix.spatial=1;CHECK(ad_render_set(&r2,&c)&&ad_render_set(&r12,&uw));
            CHECK(ad_render_process(&r2,out2,n,&a)&&ad_render_process(&r12,out12,n,&b));
            CHECK(!memcmp(raw2,raw12,n*2*sizeof(float))&&!memcmp(layers2,layers12,n*LM_SAMPLES*sizeof(float)));
            CHECK(!memcmp(&e2.drive,&e12.drive,sizeof e2.drive)&&!memcmp(&r2.dna,&r12.dna,sizeof r2.dna));
            CHECK(r2.dna.frame==r2.frame&&r2.frame==e2.frame&&r12.frame==e12.frame);
            for(unsigned j=0;j<n;++j) {
                double sample[2];float f[2];
                CHECK(telemetry[j].frame==at+j);
                if((at+j)%240==0)CHECK(sa_voice_set(&direct,telemetry[j].rpm*cfg.root_per_rpm,c.mix.detail,1));
                sa_voice_tick(&direct,sample);f[0]=(float)sample[0];f[1]=(float)sample[1];
                CHECK(!memcmp(f,raw2+2*j,sizeof f));
                anchors|=1u<<telemetry[j].lower;anchors|=1u<<telemetry[j].upper;
                for(unsigned z=0;z<2;++z){CHECK(isfinite(out2[2*j+z]));energy+=(double)f[z]*f[z];}
            }
            compare=direct;compare.bank=r2.dna.bank;CHECK(!memcmp(&compare,&r2.dna,sizeof compare));
            for(unsigned j=0;j<n*12;++j)CHECK(isfinite(out12[j]));
        }
        CHECK(energy>0&&(anchors&7)==7);
        ad_render_dispose(&r2);ad_render_dispose(&r12);dc_preset_destroy(owned);
        printf("PASS local group%u:owner poisoned/released;240123direct raw/DNA states exact;one controller;2/12six dry buses exact;all3anchors visited\n",group);
    }
    return 0;
}
