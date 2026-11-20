#include "vehicle_source/dna_assets.h"
#include "vehicle_source/internal.h"
#include "vehicle_source/atlas_adapter.h"
#include "../catalog_drive_v1/models.h"
#include <math.h>
#include <stdio.h>
#include <string.h>
#define CHECK(x) do{if(!(x)){fprintf(stderr,"DNA check line %d: %s\n",__LINE__,#x);return 3;}}while(0)
static SdProfile profiles[2];
static float first[480*2],second[480*2];
int main(void) {
    const SdProfile *models[2]={profiles,profiles+1};
    VsDnaConfig config={models,2,12,48271,VSL_V10,.02f},bad;
    VsAssets *assets;VsEngine *a,*b;VsControl control;VsOutput out={0};DcPreset *preset;
    unsigned k,n;float energy=0;
    for(k=0;k<2;++k) {
        profiles[k].rate=48000;profiles[k].window=1024;profiles[k].hop=256;
        profiles[k].harmonics=8;profiles[k].components=1;profiles[k].base_hz=20+20*k;
        profiles[k].harmonic[0].mean[0]=profiles[k].harmonic[0].mean[2]=.1f;
        profiles[k].harmonic[3].mean[0]=profiles[k].harmonic[3].mean[2]=.03f;
        profiles[k].harmonic[0].basis[0][0]=.001f;
    }
    CHECK(!vs_assets_from_dna(NULL));
    bad=config;bad.anchors=NULL;CHECK(!vs_assets_from_dna(&bad));
    bad=config;bad.count=0;CHECK(!vs_assets_from_dna(&bad));
    bad=config;bad.count=9;CHECK(!vs_assets_from_dna(&bad));
    bad=config;bad.align_orders=33;CHECK(!vs_assets_from_dna(&bad));
    bad=config;bad.seed=0;CHECK(!vs_assets_from_dna(&bad));
    bad=config;bad.vehicle_profile=-1;CHECK(!vs_assets_from_dna(&bad));
    bad=config;bad.vehicle_profile=VSL_PROFILE_COUNT;CHECK(!vs_assets_from_dna(&bad));
    bad=config;bad.root_per_rpm=NAN;CHECK(!vs_assets_from_dna(&bad));
    bad=config;bad.root_per_rpm=0;CHECK(!vs_assets_from_dna(&bad));
    bad=config;bad.root_per_rpm=.11f;CHECK(!vs_assets_from_dna(&bad));
    models[1]=NULL;CHECK(!vs_assets_from_dna(&config));models[1]=profiles+1;
    profiles[1].base_hz=20;CHECK(!vs_assets_from_dna(&config));profiles[1].base_hz=40;
    profiles[1].harmonics=7;CHECK(!vs_assets_from_dna(&config));profiles[1].harmonics=8;
    profiles[1].rho[0]=1;CHECK(!vs_assets_from_dna(&config));profiles[1].rho[0]=0;
    assets=vs_assets_from_dna(&config);CHECK(assets&&at_assets_valid(&assets->owned));
    CHECK(assets->owned.bank.profile[0]==&assets->owned.profile[0]);
    CHECK(!assets->owned.config.recipe_bank&&!assets->owned.config.residual_bank&&!assets->owned.config.resonant_bank);
    CHECK(!assets->owned.config.idle_profile&&!assets->owned.config.fine_idle_profile);
    CHECK(!assets->owned.config.startup_profile&&!assets->owned.config.catch_profile);
    memset(profiles,0,sizeof profiles);CHECK(at_assets_valid(&assets->owned));
    preset=cd_models_load(0);CHECK(preset);
    {AdControl initial=dc_preset_initial(preset);vs_control_from_atlas(&initial,&control);}
    dc_preset_destroy(preset);control.mode=VS_BENCH;control.rpm=1500;control.ignition=1;control.start_id=1;
    control.events.enabled=0;control.legacy_event_gain=0;
    control.low_mix=control.coherent_low_gain=control.resonant_gain=control.residual_gain=0;
    control.startup_gain=control.catch_gain=control.idle_mix=control.idle_motion=control.idle_detail=0;
    control.intake_gain=control.mechanical_gain=control.air_gain=control.road_gain=control.wind_gain=0;
    control.low_mix=control.coherent_low_gain=control.resonant_gain=control.residual_gain=0;
    control.startup_gain=control.catch_gain=control.idle_mix=control.idle_motion=control.idle_detail=0;
    control.intake_gain=control.mechanical_gain=control.air_gain=control.road_gain=control.wind_gain=0;
    a=vs_engine_create(assets,&control);b=vs_engine_create(assets,&control);CHECK(a&&b);
    out.monitor=first;
    for(k=0;k<120;++k) {
        CHECK(vs_engine_process(a,&out,480));out.monitor=second;
        CHECK(vs_engine_process(b,&out,480));CHECK(!memcmp(first,second,sizeof first));out.monitor=first;
        for(n=0;n<960;++n){CHECK(isfinite(first[n]));energy+=first[n]*first[n];}
    }
    CHECK(energy>0);vs_engine_destroy(a);vs_engine_destroy(b);vs_assets_destroy(assets);
    puts("PASS owned authored DNA, invalid configs, no inherited optional assets and deterministic generation");return 0;
}
