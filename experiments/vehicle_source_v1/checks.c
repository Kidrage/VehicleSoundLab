#include "vehicle_source/internal.h"
#include "atlas_drive/source_process.h"
#include "../catalog_drive_v1/models.h"
#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#define N 1024
#define CHECK(x) do{if(!(x)){fprintf(stderr,"source check line%d: %s\n",__LINE__,#x);goto done;}}while(0)
static float monitor[N*2],old_output[N*2],old_dry[N*2],split[N*2],stems[VS_STEMS][N*2];
static int run(int selection) {
    DcPreset *p=NULL;VsAssets *assets=NULL;VsEngine *engine=NULL,*partitioned=NULL;
    VslEngine *old_owner=NULL;AdRender *legacy=NULL;VslSpatial *unchanged=NULL;
    VsControl c,invalid;VsOutput out={0},split_out={0};AdControl old;AdCapture capture={0};
    VsTelemetry state;unsigned at=0,n,k,j;double error=0,energy=0;int ok=0;
    CHECK(p=cd_models_load(selection));old=dc_preset_initial(p);
    old.drive.ignition=old.drive.start_id=1;old.drive.mode=VSL_BENCH;
    old.mix.intake_gain=.2;old.mix.mechanical_gain=.25;old.mix.air_gain=.2;old.mix.road_gain=.1;old.mix.wind_gain=.1;
    old.mix.event_gain=.3;old.mix.room=.45;old.mix.spatial=1;old.mix.propagation=1;
    vs_control_from_atlas(&old,&c);
    CHECK(assets=vs_assets_from_atlas(dc_preset_config(p)));
    CHECK(engine=vs_engine_create(assets,&c));CHECK(partitioned=vs_engine_create(assets,&c));
    CHECK(old_owner=calloc(1,sizeof *old_owner));CHECK(legacy=calloc(1,sizeof *legacy));
    CHECK(unchanged=malloc(sizeof *unchanged));
    /* Both paths borrow the independently owned copy. ad_render_init does not
       own the preset models, so destroying p must not invalidate the oracle. */
    CHECK(ad_render_init(legacy,old_owner,&assets->owned.config,&old));
    dc_preset_destroy(p);p=NULL; /* Asset source may now be released. */
    memcpy(unchanged,&engine->owner.spatial,sizeof *unchanged);
    out.monitor=monitor;split_out.monitor=split;
    for(k=0;k<VS_STEMS;++k)out.stem[k]=stems[k];
    capture.dry=old_dry;
    for(at=0;at<134400;at+=n) {
        n=134400-at>N?N:134400-at;
        const unsigned edges[]={43200,76800,105600,134400};
        for(j=0;j<4;++j)if(edges[j]>at&&edges[j]-at<n)n=edges[j]-at;
        if(at==43200){c.rpm=6500;c.load=.7;c.gain=.18;}
        if(at==76800){c.rpm=850;c.load=-.5;c.gain=.25;}
        if(at==105600)c.ignition=0;
        CHECK(vs_engine_set(engine,&c)&&vs_engine_set(partitioned,&c));
        vs_control_to_atlas(&c,&old);old.mix.room=.45;old.mix.spatial=1;old.mix.propagation=1;
        CHECK(ad_render_set(legacy,&old));
        CHECK(ad_render_process(legacy,old_output,n,&capture));
        CHECK(vs_engine_process(engine,&out,n));
        CHECK(!memcmp(monitor,old_dry,n*2*sizeof(float)));
        CHECK(!memcmp(&engine->owner.drive,&old_owner->drive,sizeof old_owner->drive));
        CHECK(!memcmp(unchanged,&engine->owner.spatial,sizeof *unchanged));
        for(j=0;j<n;) {
            unsigned count=n-j>73?73:n-j;split_out.monitor=split+2*j;
            CHECK(vs_engine_process(partitioned,&split_out,count));j+=count;
        }
        CHECK(!memcmp(monitor,split,n*2*sizeof(float)));
        for(j=0;j<n;++j)for(unsigned channel=0;channel<2;++channel) {
            double sum=0;
            for(k=0;k<VS_STEMS;++k) {
                const VsStemInfo *m=vs_stem_info(k);
                unsigned which=m->channels==1?0:channel;
                double weight=channel?m->monitor_right:m->monitor_left;
                float x=stems[k][j*m->channels+which];CHECK(isfinite(x));sum+=x*weight;
            }
            error=fmax(error,fabs(sum-monitor[2*j+channel]));
            CHECK(fabs(sum-monitor[2*j+channel])<2e-6);
            CHECK(isfinite(monitor[2*j+channel]));energy+=(double)monitor[2*j+channel]*monitor[2*j+channel];
        }
    }
    CHECK(energy>0&&vs_engine_telemetry(engine,&state)&&state.frame==134400);
    invalid=c;invalid.rpm=NAN;CHECK(!vs_engine_set(engine,&invalid));
    CHECK(!vs_engine_process(engine,&out,VS_BLOCK_MAX+1));
    out.stem[VS_DNA]=monitor;CHECK(!vs_engine_process(engine,&out,1));out.stem[VS_DNA]=stems[VS_DNA];
    CHECK(vs_engine_telemetry(engine,&state)&&state.frame==134400);
    CHECK(vs_stem_info(VS_STEMS)==NULL);
    {AdCapture bad={0};bad.objects=stems[0];CHECK(!ad_source_process(&engine->generator,monitor,1,&bad));}
    printf("PASS source preset%d: dry bit-exact, driver exact, spatial untouched, block-independent, stem error %.9g\n",selection,error);ok=1;
done:
    if(legacy)ad_render_dispose(legacy);free(legacy);free(old_owner);free(unchanged);
    vs_engine_destroy(engine);vs_engine_destroy(partitioned);vs_assets_destroy(assets);dc_preset_destroy(p);return ok;
}
int main(void){for(int k=0;k<DC_COUNT;++k)if(!run(k))return 3;return 0;}
