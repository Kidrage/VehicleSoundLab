#include "vehicle_source/state_assets.h"
#include "vehicle_source/internal.h"
#include "state_dna/lookup.h"
#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#define PI 3.14159265358979323846
#define CHECK(x) do{if(!(x)){fprintf(stderr,"state DNA line %d: %s\n",__LINE__,#x);return 3;}}while(0)
static SdProfile model[4];static SaBank bank[4];static SxBank blend;
static SaVoice main_voice,reference;static SxVoice voice;
static void profile(SdProfile *p,double hz,double amplitude,double phase) {
    memset(p,0,sizeof *p);p->rate=48000;p->window=1024;p->hop=256;p->harmonics=8;p->base_hz=hz;
    p->harmonic[0].mean[0]=amplitude*cos(phase);p->harmonic[0].mean[1]=amplitude*sin(phase);
    p->harmonic[0].mean[2]=amplitude*cos(phase+.2);p->harmonic[0].mean[3]=amplitude*sin(phase+.2);
}
int main(void) {
    const SaBank *donors[3]={0};const SdProfile *models[4];HbBand body=hb_band_default();
    unsigned s,n,c;double out[2],low[2],ref[2],ref_low[2],max_error=0;SxTelemetry stats;
    for(s=0;s<4;++s){profile(model+s,30,.1+.03*s,.2*s);models[s]=model+s;
        CHECK(sa_bank_init(bank+s,models+s,1,0));}
    CHECK(sx_bank_init(&blend,bank,donors,0,.1));CHECK(sx_voice_init(&voice,&blend,93));
    CHECK(sa_voice_init(&main_voice,bank,93,30,.7,1));reference=main_voice;
    CHECK(sx_voice_select(&voice,SX_IDLE));CHECK(voice.target[0]==1);
    for(n=0;n<9600;++n){CHECK(sx_voice_tick(&voice,&main_voice,&body,out,low));
        CHECK(sa_voice_tick_body(&reference,&body,ref,ref_low));
        CHECK(!memcmp(out,ref,sizeof out)&&!memcmp(low,ref_low,sizeof low));}
    CHECK(main_voice.frame==reference.frame&&main_voice.phase==reference.phase);
    donors[1]=bank+2;CHECK(sx_bank_init(&blend,bank,donors,0,.1));
    CHECK(sx_voice_init(&voice,&blend,93));CHECK(sa_voice_init(&main_voice,bank,93,30,0,1));
    CHECK(sx_voice_select(&voice,SX_POWER));
    for(n=0;n<48000;++n){double phase=main_voice.phase;CHECK(sx_voice_tick(&voice,&main_voice,&body,out,low));
        double w=1-exp(-(double)(n+1)/4800.);CHECK(fabs(voice.weight[2]-w)<2e-13);
        for(c=0;c<2;++c){double expected=(.1+.06*w)*cos(phase+.2*c+.4*w);
            max_error=fmax(max_error,fabs(out[c]-expected));CHECK(fabs(out[c]-expected)<1e-7);}}
    CHECK(main_voice.frame==48000&&voice.frame==48000);
    CHECK(sx_voice_telemetry(&voice,&stats)&&stats.available_mask==5&&stats.target[2]==1);
    CHECK(!sx_voice_select(&voice,4));
    CHECK(!sx_bank_init(&blend,bank,donors,33,.1));CHECK(!sx_bank_init(&blend,bank,donors,0,NAN));
    CHECK(!sx_bank_init(&blend,bank,donors,0,.019));CHECK(!sx_bank_init(&blend,bank,donors,0,2.01));
    {VsStateDnaConfig config={0},bad;VsAssets *assets;VsControl control={0};VsEngine *engine;
        config.anchors[0]=models;config.count[0]=1;config.anchors[1]=models+1;config.count[1]=1;
        config.seed=93;config.vehicle_profile=VSL_V10;config.root_per_rpm=.02;config.transition_seconds=.1;
        assets=vs_assets_from_state_dna(&config);CHECK(assets);
        bad=config;bad.count[0]=0;CHECK(!vs_assets_from_state_dna(&bad));
        bad=config;bad.count[1]=0;CHECK(!vs_assets_from_state_dna(&bad));
        bad=config;bad.count[1]=9;CHECK(!vs_assets_from_state_dna(&bad));
        bad=config;bad.transition_seconds=NAN;CHECK(!vs_assets_from_state_dna(&bad));
        model[1].harmonics=7;CHECK(!vs_assets_from_state_dna(&config));
        memset(model,0,sizeof model);control.events=ec_default();control.events.enabled=0;
        control.mode=VS_BENCH;control.rpm=850;control.ignition=1;control.start_id=1;control.gain=.1;
        engine=vs_engine_create(assets,&control);CHECK(engine);
        VslSpatial spatial=engine->owner.spatial;
        VsOutput output={0};float audio[960];output.monitor=audio;
        for(n=0;n<500;++n)CHECK(vs_engine_process(engine,&output,480));
        CHECK(vs_engine_state_dna(engine,&stats)&&stats.target[SX_IDLE]==1&&stats.weight[SX_IDLE]>.99);
        CHECK(engine->state_dna.frame==240000&&engine->generator.dna.frame==240000&&engine->generator.frame==240000);
        CHECK(isfinite(engine->generator.dna.phase)&&engine->generator.dna.phase>=0&&engine->generator.dna.phase<2*PI);
        CHECK(!memcmp(&spatial,&engine->owner.spatial,sizeof spatial));
        vs_engine_destroy(engine);vs_assets_destroy(assets);
    }
    printf("PASS one-clock state DNA, analytic phase/magnitude %.9g, base exact, owned states and driver selection\n",max_error);
    return 0;
}
