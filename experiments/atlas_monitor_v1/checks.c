#include "atlas_monitor/render.h"
#include "core/engine.h"
#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#define CHECK(x) do{if(!(x)){fprintf(stderr,"monitor check line%d: %s\n",__LINE__,#x);return 1;}}while(0)
static SdProfile a,b;static SaBank bank;
static VslEngine engine1,engine2;static AmRender render;static AdRender reference;
static float whole[2048],split[2048],raw[2048];
int main(int argc,char **argv) {
    const SdProfile *models[2]={&a,&b};unsigned n;
    AdConfig config={&bank,48271,VSL_V10,2,1./120,DS_OBSERVE_MID,DS_ROUTE_PAIR};
    AdControl control={{VSL_BENCH,1,1,1,0,1,5000,.8,0,0},{.25,1,0,.7,0,0,0,0}};
    CHECK(argc==3&&sd_profile_load(argv[1],&a)&&sd_profile_load(argv[2],&b));
    CHECK(sa_bank_init(&bank,models,2,32));
    CHECK(am_render_init(&render,&engine1,&config,&control)&&ad_render_init(&reference,&engine2,&config,&control));
    CHECK(am_render_process(&render,whole,1024,0,NULL)&&ad_render_process(&reference,raw,1024,NULL));
    for(n=0;n<2048;++n) {
        float gain=n/2<480?(float)((n/2)/480.):1;
        CHECK(whole[n]==raw[n]*gain);
    }
    CHECK(am_render_init(&render,&engine1,&config,&control));
    for(n=0;n<1024;++n)CHECK(am_render_process(&render,split+2*n,1,0,NULL));
    CHECK(!memcmp(whole,split,sizeof whole));
    CHECK(am_render_process(&render,whole,1024,1,NULL)&&render.release==480);
    for(n=960;n<2048;++n)CHECK(whole[n]==0);
    CHECK(am_render_process(&render,whole,1024,0,NULL));
    for(n=0;n<2048;++n)CHECK(whole[n]==0);
    CHECK(am_render_init(&render,&engine1,&config,&control));
    control.drive.throttle=NAN;CHECK(!am_render_set(&render,&control));
    CHECK(!am_render_process(&render,whole,1,2,NULL));
    {
        float stereo_source[128],surround_source[128];
        AdCapture cap2={stereo_source,0,0,0,0,0},cap12={surround_source,0,0,0,0,0};
        control.drive.throttle=0;control.mix.spatial=1;
        CHECK(ad_render_init(&reference,&engine2,&config,&control));
        CHECK(ad_render_process(&reference,raw,64,&cap2));
        config.channels=12;
        CHECK(am_render_init(&render,&engine1,&config,&control));
        CHECK(am_render_process(&render,whole,64,0,&cap12));
        CHECK(!memcmp(stereo_source,surround_source,sizeof stereo_source));
        for(n=0;n<64;++n)for(unsigned c=8;c<12;++c)CHECK(whole[n*12+c]==0);
    }
    puts("monitor transport/source parity, block independence and irreversible release passed");return 0;
}
