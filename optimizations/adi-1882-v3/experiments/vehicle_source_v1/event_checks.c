#include "vehicle_source/atlas_adapter.h"
#include "../catalog_drive_v1/models.h"
#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#define CHECK(x) do{if(!(x)){fprintf(stderr,"source event line%d: %s\n",__LINE__,#x);goto done;}}while(0)
static float a[2048],b[2048],stems[VS_STEMS][2048];
int main(void) {
    DcPreset *preset=NULL;VsAssets *assets=NULL;VsEngine *one=NULL,*split=NULL;
    VsControl control;VsOutput out={0},partitioned={0};VsTelemetry state;
    EsNotice first[128],second[128];unsigned n,j,k,count1,count2,cranks=0,catches=0;int ok=0;float energy=0,error=0;
    CHECK(preset=cd_models_load(0));AdControl old=dc_preset_initial(preset);vs_control_from_atlas(&old,&control);
    CHECK(assets=vs_assets_from_atlas(dc_preset_config(preset)));dc_preset_destroy(preset);preset=NULL;
    control.events.enabled=1;control.events.gain=.4f;control.ignition=0;control.start_id=0;
    CHECK(one=vs_engine_create(assets,&control));CHECK(split=vs_engine_create(assets,&control));
    out.monitor=a;partitioned.monitor=b;CHECK(vs_engine_process(one,&out,137)&&vs_engine_process(split,&partitioned,137));
    control.events.manual_type=ES_CATCH;control.events.manual_sequence=1;
    CHECK(vs_engine_set(one,&control)&&vs_engine_set(split,&control));
    for(unsigned at=137;at<48000;at+=n) {
        n=48000-at>1024?1024:48000-at;
        CHECK(vs_engine_process(one,&out,n));
        for(j=0;j<n;) {unsigned part=n-j>37?37:n-j;partitioned.monitor=b+2*j;CHECK(vs_engine_process(split,&partitioned,part));j+=part;}
        CHECK(!memcmp(a,b,n*2*sizeof(float)));
    }
    count1=vs_engine_events(one,first,128);count2=vs_engine_events(split,second,128);
    CHECK(count1==2&&count1==count2&&!memcmp(first,second,count1*sizeof *first));
    CHECK(first[0].frame==137&&first[0].requested_frame==137&&first[0].action==ES_STARTED);
    CHECK(first[1].frame==38537&&first[1].action==ES_ENDED&&first[0].id==first[1].id);
    vs_engine_destroy(one);one=NULL;vs_engine_destroy(split);split=NULL;
    control.events.manual_sequence=0;control.events.manual_type=ES_CRANK;control.ignition=control.start_id=1;
    CHECK(one=vs_engine_create(assets,&control));
    for(k=0;k<VS_STEMS;++k)out.stem[k]=stems[k];
    for(unsigned at=0;at<144000;at+=n) {
        n=144000-at>1024?1024:144000-at;CHECK(vs_engine_process(one,&out,n));
        for(j=0;j<n;++j)for(unsigned channel=0;channel<2;++channel) {
            float sum=0;
            for(k=0;k<VS_STEMS;++k) {
                const VsStemInfo *info=vs_stem_info(k);float x=stems[k][j*info->channels+(info->channels==2?channel:0)];
                CHECK(isfinite(x));sum+=x*(channel?info->monitor_right:info->monitor_left);
                if(k>=VS_EVENT_0)energy+=x*x;
            }
            CHECK(stems[VS_LEGACY_EVENT][j]==0&&stems[VS_STARTUP][2*j+channel]==0&&stems[VS_CATCH][2*j+channel]==0);
            error=fmaxf(error,fabsf(sum-a[2*j+channel]));CHECK(fabsf(sum-a[2*j+channel])<2e-6f);
        }
    }
    CHECK(vs_engine_telemetry(one,&state));CHECK(energy>0&&state.event_peak<=4&&state.event_log_lost==0&&state.event_overflow==0);
    count1=vs_engine_events(one,first,128);
    for(k=0;k<count1;++k)if(first[k].action==ES_STARTED){cranks+=first[k].type==ES_CRANK;catches+=first[k].type==ES_CATCH;}
    CHECK(cranks==1&&catches==1);
    vs_engine_destroy(one);one=NULL;control.events.decay=4;
    CHECK(one=vs_engine_create(assets,&control));
    for(unsigned at=0;at<21600;at+=n) {n=21600-at>1024?1024:21600-at;CHECK(vs_engine_process(one,&out,n));}
    control.ignition=0;CHECK(vs_engine_set(one,&control));
    for(unsigned at=21600;at<96000;at+=n) {
        n=96000-at>1024?1024:96000-at;CHECK(vs_engine_process(one,&out,n));
        if(at>=48000)for(k=VS_EVENT_0;k<VS_STEMS;++k)for(j=0;j<n;++j)CHECK(stems[k][j]==0);
    }
    CHECK(vs_engine_telemetry(one,&state)&&state.lifecycle==0&&state.event_active==0);
    count1=vs_engine_events(one,first,128);unsigned catch_release=0;
    for(k=0;k<count1;++k)if(first[k].type==ES_CATCH&&first[k].action==ES_ENDED) {
        CHECK(first[k].frame==22560&&first[k].reason==ES_RELEASED);++catch_release;
    }
    CHECK(catch_release==1);
    printf("PASS source event exact frame137, block identity/audio, unique startup edges, startup abort release, native23ch reconstruction error %.9g\n",error);ok=1;
done:
    vs_engine_destroy(one);vs_engine_destroy(split);vs_assets_destroy(assets);dc_preset_destroy(preset);return ok?0:3;
}
