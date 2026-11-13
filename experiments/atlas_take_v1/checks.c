#include "atlas_take/player.h"
#include "atlas_take_io/file.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>
#include <limits.h>
#define CHECK(x) do{if(!(x)){fprintf(stderr,"take check line%d: %s\n",__LINE__,#x);return 1;}}while(0)
static SdProfile models[2];static SaBank bank;static RaBank residual;
static AmRender render;static VslEngine engine,other;static AtPlayer player;
static float original[12000*2],replay[12000*2],surround[512*12];
static float raw[1024],dna[1024],noise[1024],body[1024],event[512];
static float auxiliary[512*VSL_OBJECTS];
static float startup[1024];
static float catch_bloom[1024];
static CbProfile catch_profile={1,1,2,.005,.035,{{100,1,2}}};
static StProfile startup_profile;
static uint64_t bytes_hash(const unsigned char *p,size_t n) {
    uint64_t h=AT_HASH_INITIAL;size_t i;for(i=0;i<n;++i){h^=p[i];h*=UINT64_C(1099511628211);}return h;
}
static void rehash(unsigned char *p,size_t n) {uint64_t h=bytes_hash(p,n-8);unsigned i;for(i=0;i<8;++i)p[n-8+i]=(unsigned char)(h>>(8*i));}
int main(void) {
    const SdProfile *p[2]={models,models+1};AtTake take={0},loaded={0},tiny={0};
    AdControl c={{VSL_BENCH,1,1,1,0,1,3600,.8,0,0},{.2,1,.2,.7,.2,0,1,1,.5,.6}};
    AdConfig config={&bank,48271,VSL_V10,2,1./120,DS_OBSERVE_MID,DS_ROUTE_PAIR,&residual};
    AdCapture capture={0};unsigned i,h,k;uint64_t source=AT_HASH_INITIAL,hash=AT_HASH_INITIAL,at=0;
    unsigned char *data=NULL,*data2=NULL;size_t size=0,size2=0;AtAssets *saved;
    for(i=0;i<2;++i) {
        SdProfile *m=models+i;m->rate=48000;m->window=1024;m->hop=256;m->base_hz=20+i*40;m->harmonics=24;m->components=1;m->rho[0]=.4;
        for(h=0;h<m->harmonics;++h){m->harmonic[h].rho=.3;for(k=0;k<2;++k){m->harmonic[h].mean[2*k]=.02*cos(h*.2+k*.3)/(h+1);
            m->harmonic[h].mean[2*k+1]=.02*sin(h*.2+k*.3)/(h+1);m->harmonic[h].basis[0][2*k]=.001/(h+1);m->harmonic[h].root[2*k][2*k]=.0001;}}
        residual.root[i]=m->base_hz;residual.profile[i].rate=48000;residual.profile[i].bands=1;residual.profile[i].partials=32;
        residual.profile[i].band[0]=(SrBand){1200,3000,{.00001,.00002},{.4,.2}};
    }
    residual.count=2;CHECK(sa_bank_init(&bank,p,2,16)&&ra_bank_valid(&residual));
    config.scene_mode=AD_SCENE_STEREO_BED;
    startup_profile.spectrum.rate=48000;startup_profile.spectrum.bands=1;startup_profile.spectrum.partials=8;
    startup_profile.spectrum.band[0]=(SrBand){300,900,{.001,.002},{.4,.2}};
    startup_profile.has_finish=1;startup_profile.finish=startup_profile.spectrum;
    startup_profile.finish.band[0].power[0]=.002;startup_profile.attack_seconds=.005;startup_profile.release_seconds=.035;
    config.startup_profile=&startup_profile;c.mix.startup_gain=.5;
    config.catch_profile=&catch_profile;c.mix.catch_gain=.5;
    CHECK(at_take_allocate(&take,32)&&!at_take_allocate(&take,32));
    c.mix.intake_gain=.5;c.mix.mechanical_gain=.4;c.mix.air_gain=.3;c.mix.road_gain=.2;c.mix.wind_gain=.1;
    CHECK(at_take_begin(&take,&config,&c));
    saved=take.assets;config.root_per_rpm=NAN;CHECK(!at_take_begin(&take,&config,&c)&&take.assets==saved);config.root_per_rpm=1./120;
    CHECK(am_render_init(&render,&engine,&take.assets->config,&c));
    c.mix.gain=.3;CHECK(at_take_event(&take,0,&c)&&am_render_set(&render,&c));
    capture.dna_raw=raw;capture.dna=dna;capture.residual=noise;capture.body=body;capture.events=event;
    capture.aux_objects=auxiliary;
    capture.startup=startup;
    capture.catch_bloom=catch_bloom;
    while(at<12000) {
        unsigned n=257;if(n>12000-at)n=(unsigned)(12000-at);
        if(at<3001&&at+n>3001)n=(unsigned)(3001-at);
        if(at<7777&&at+n>7777)n=(unsigned)(7777-at);
        if(at<11493&&at+n>11493)n=(unsigned)(11493-at);
        if(at==3001){c.drive.rpm=6500;c.mix.body_mix=1;c.mix.residual_gain=.8;c.mix.intake_gain=.8;c.mix.mechanical_gain=1;CHECK(at_take_event(&take,at,&c)&&am_render_set(&render,&c));}
        if(at==7777){c.mix.spatial=0;c.mix.body_mix=0;c.mix.detail=.4;c.mix.air_gain=0;c.mix.road_gain=1;c.mix.wind_gain=.7;CHECK(at_take_event(&take,at,&c)&&am_render_set(&render,&c));}
        if(at==11493)take.stop_frame=at;
        CHECK(am_render_process(&render,original+2*at,n,at>=take.stop_frame,&capture));
        source=at_hash_sources(source,&capture,n);hash=at_hash_samples(hash,original+2*at,n*2);
        CHECK(at_take_commit(&take,n,hash,source));at+=n;
    }
    CHECK(at_take_event(&take,at,&c));at_take_finish(&take);CHECK(take.count==3&&at_take_valid(&take));
    CHECK(!at_take_commit(&take,UINT_MAX,hash,source));
    memset(models,0,sizeof models);memset(&bank,0,sizeof bank);memset(&residual,0,sizeof residual);
    memset(&startup_profile,0,sizeof startup_profile);
    memset(&catch_profile,0,sizeof catch_profile);
    CHECK(at_player_init(&player,&other,&take,2));
    for(i=0;i<12000;) {unsigned n=1+(i*17)%731;if(n>12000-i)n=12000-i;CHECK(at_player_process(&player,replay+2*i,n,NULL)==n);i+=n;}
    CHECK(at_player_verified(&player)&&!memcmp(original,replay,sizeof original));
    CHECK(at_player_init(&player,&other,&take,12));while(!at_player_complete(&player))CHECK(at_player_process(&player,surround,512,NULL)>0);
    CHECK(at_player_verified(&player)&&player.source_hash==source);
    CHECK(at_take_encode(&take,&data,&size)&&at_take_decode(&loaded,data,size));
    CHECK(loaded.assets->config.scene_mode==AD_SCENE_STEREO_BED);
    CHECK(loaded.assets->config.startup_profile==&loaded.assets->startup&&loaded.assets->startup.has_finish==1);
    CHECK(loaded.assets->config.catch_profile==&loaded.assets->catch_bloom&&loaded.assets->catch_bloom.mode[0].gain==2);
    CHECK(at_take_encode(&loaded,&data2,&size2)&&size==size2&&!memcmp(data,data2,size));free(data2);data2=NULL;
    saved=loaded.assets;data[100]^=1;CHECK(!at_take_decode(&loaded,data,size)&&loaded.assets==saved);data[100]^=1;
    data[104]=7;rehash(data,size);CHECK(!at_take_decode(&loaded,data,size)&&loaded.assets==saved);data[104]=1;rehash(data,size);
    CHECK(!at_take_decode(&loaded,data,size-1)&&loaded.assets==saved);
    data[12]^=1;rehash(data,size);CHECK(!at_take_decode(&loaded,data,size)&&loaded.assets==saved);data[12]^=1;rehash(data,size);
    data[8]=7;rehash(data,size);CHECK(!at_take_decode(&loaded,data,size)&&loaded.assets==saved);data[8]=10;rehash(data,size);
    CHECK(at_take_decode(&loaded,data,size));saved=loaded.assets;
    data[76]^=1;rehash(data,size);CHECK(!at_take_decode(&loaded,data,size)&&loaded.assets==saved);data[76]^=1;rehash(data,size);
    data2=malloc(size+1);CHECK(data2);memcpy(data2,data,size-8);data2[size-8]=0;rehash(data2,size+1);
    CHECK(!at_take_decode(&loaded,data2,size+1)&&loaded.assets==saved);free(data2);
    CHECK(at_take_save(&take,"atlas take test.vslrun")&&at_take_load(&loaded,"atlas take test.vslrun"));
    c=take.initial;take.initial.mix.gain=NAN;
    CHECK(!at_take_save(&take,"atlas take test.vslrun"));take.initial=c;
    CHECK(at_take_load(&loaded,"atlas take test.vslrun")&&loaded.audio_hash==take.audio_hash);
    CHECK(!at_take_save(&take,"not-a-directory/take.vslrun")&&!at_take_load(&loaded,"missing.vslrun")&&loaded.assets);
    CHECK(at_player_init(&player,&other,&loaded,2));while(!at_player_complete(&player))CHECK(at_player_process(&player,replay,512,NULL)>0);
    CHECK(at_player_verified(&player));remove("atlas take test.vslrun");
    CHECK(at_take_allocate(&tiny,1)&&at_take_begin(&tiny,&take.assets->config,&take.initial)&&at_take_event(&tiny,0,&take.initial));
    CHECK(at_take_commit(&tiny,1,hash,source));c=take.initial;c.mix.gain=.1;
    CHECK(!at_take_event(&tiny,1,&c)&&tiny.overflow&&!at_take_valid(&tiny));
    printf("PASS: owned assets, initial/frame0, arbitrary controls/stop/chunks, stereo/12source hashes, codec exact %zu bytes, corruption and transactional files\n",size);
    free(data);at_take_free(&take);at_take_free(&loaded);at_take_free(&tiny);return 0;
}
