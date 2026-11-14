#define _CRT_SECURE_NO_WARNINGS
#include "atlas_monitor/render.h"
#include "atlas_take/player.h"
#include "atlas_take_io/file.h"
#include "io/file.h"
#include "../fine_idle_drive_v1/models.h"
#include "../full_recipe_drive_v1/models.h"
#ifndef LM_LEGACY
#include "layer_monitor/listen.h"
#endif
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>
#define CHECK(x) do{if(!(x)){fprintf(stderr,"canonical%d: %s\n",__LINE__,#x);goto done;}}while(0)
#define FRAMES 384123u
static FidModels idle;static FrModels moving;static AmRender render;static VslEngine engine;
static float raw[1024],dna[1024],body[1024],residual[1024],resonant[1024],lowraw[1024],low[1024];
static float aux[512*VSL_OBJECTS],events[512],startup[1024],catching[1024],idleraw[1024],idlesound[1024],core[1024],detail[1024],dry[1024];
static AdTelemetry telemetry[512];static AtPlayer player;
#ifndef LM_LEGACY
static float layers[512*LM_SAMPLES],heard[1024];
#endif
static unsigned block(unsigned at,unsigned maximum) {
    const unsigned cuts[]={96000,192000,240000,288000,336000,FRAMES-480,FRAMES};unsigned n=FRAMES-at;
    if(n>maximum)n=maximum;for(unsigned i=0;i<sizeof cuts/sizeof cuts[0];++i)if(cuts[i]>at&&cuts[i]-at<n)n=cuts[i]-at;
    return n;
}
static void event(unsigned at,AdControl *c) {
    if(at==96000){c->drive.rpm=6500;c->drive.load=.7;}
    if(at==192000)c->drive.load=-.6;
    if(at==240000){c->drive.rpm=850;c->drive.load=0;}
    if(at==288000)c->drive.ignition=0;
    if(at==336000){c->drive.ignition=1;++c->drive.start_id;}
}
static int run(const char *root,int fine,int channels) {
    AdConfig cfg={0};AdControl c={0};AdCapture cap={0};AtTake take={0},loaded={0};
    FILE *wave=NULL,*trace=NULL,*stem=NULL,*report=NULL;char path[4096],tag[32];float *reference=NULL,out[512*12];
    uint64_t ah=AT_HASH_INITIAL,sh=AT_HASH_INITIAL;unsigned at,n;double maximum_error=0,energy[6]={0},peak=0;int ok=0;
    snprintf(tag,sizeof tag,"%s%d",fine?"fine":"base",channels);
    cfg.bank=&moving.bank;cfg.seed=48271;cfg.profile=VSL_V10;cfg.channels=channels;cfg.root_per_rpm=1./120;
    cfg.scene_mode=AD_SCENE_STEREO_BED;cfg.resonant_bank=&moving.resonance;cfg.recipe_bank=&moving.recipe;
    if(fine)cfg.fine_idle_profile=&idle.idle;
    c.drive.mode=VSL_BENCH;c.drive.ignition=c.drive.start_id=c.drive.backfire=1;c.drive.gear=1;c.drive.rpm=850;
    c.mix.gain=.18;c.mix.detail=c.mix.width=c.mix.resonant_gain=c.mix.coherent_low_gain=1;c.mix.event_gain=.3;
    c.mix.intake_gain=c.mix.mechanical_gain=c.mix.air_gain=.12;c.mix.spatial=channels==12;
    if(fine){c.mix.idle_mix=c.mix.idle_detail=1;c.mix.idle_motion=.5;}
    cap.dna_raw=raw;cap.dna=dna;cap.body=body;cap.residual=residual;cap.events=events;cap.aux_objects=aux;
    cap.startup=startup;cap.catch_bloom=catching;cap.resonant=resonant;cap.coherent_low_raw=lowraw;cap.coherent_low=low;
    if(fine){cap.idle_modal=core;cap.idle_detail=detail;cap.idle_raw=idleraw;cap.idle=idlesound;}
    cap.telemetry=telemetry;cap.dry=dry;
#ifndef LM_LEGACY
    cap.layers=layers;
    snprintf(path,sizeof path,"%s/%s_layers.bin",root,tag);stem=vsl_fopen(path,"wb");CHECK(stem);
#endif
    CHECK(at_take_allocate(&take,32)&&at_take_begin(&take,&cfg,&c)&&am_render_init(&render,&engine,&cfg,&c));
    reference=calloc((size_t)FRAMES*channels,sizeof(float));CHECK(reference);
    snprintf(path,sizeof path,"%s/%s_pcm.bin",root,tag);wave=vsl_fopen(path,"wb");CHECK(wave);
    snprintf(path,sizeof path,"%s/%s_trace.csv",root,tag);trace=vsl_fopen(path,"wb");CHECK(trace);
    fputs("frame,rpm,speed,load,gear,lifecycle,operating,shifts,overruns,hits\n",trace);
    for(at=0;at<FRAMES;at+=n) {
        n=block(at,257);event(at,&c);CHECK(at_take_event(&take,at,&c)&&am_render_set(&render,&c));
        if(at==FRAMES-480)take.stop_frame=at;
        CHECK(am_render_process(&render,reference+(size_t)at*channels,n,at>=FRAMES-480,&cap));
        ah=at_hash_samples(ah,reference+(size_t)at*channels,n*channels);sh=at_hash_sources(sh,&cap,n);
        CHECK(at_take_commit(&take,n,ah,sh));
        CHECK(fwrite(reference+(size_t)at*channels,sizeof(float),n*channels,wave)==n*channels);
        for(unsigned j=0;j<n;++j) {
            AdTelemetry *t=&telemetry[j];
            if((at+j)%240==0)fprintf(trace,"%llu,%.17g,%.17g,%.17g,%d,%d,%d,%u,%u,%u\n",(unsigned long long)t->frame,t->rpm,t->speed,t->load,t->gear,t->lifecycle,t->operating,t->shifts,t->overruns,t->hits);
            for(int k=0;k<channels;++k)peak=fmax(peak,fabs(reference[((size_t)at+j)*channels+k]));
#ifndef LM_LEGACY
            double fade=at+j<480?(at+j)/480.:1.;if(at+j>=FRAMES-480)fade*=1-(at+j-(FRAMES-480)+1)/480.;
            for(int cc=0;cc<2;++cc) {
                double sum=0;for(int k=0;k<LM_LAYERS;++k){double x=layers[j*LM_SAMPLES+2*k+cc];sum+=x;energy[k]+=x*x;}
                maximum_error=fmax(maximum_error,fabs(sum-(float)(dry[2*j+cc]*(float)fade)));
            }
#endif
        }
#ifndef LM_LEGACY
        CHECK(fwrite(layers,sizeof(float),n*LM_SAMPLES,stem)==n*LM_SAMPLES);
#endif
    }
    CHECK(!fclose(wave));wave=NULL;CHECK(!fclose(trace));trace=NULL;
    at_take_finish(&take);CHECK(at_take_valid(&take));
    snprintf(path,sizeof path,"%s/%s.vslrun",root,tag);CHECK(at_take_save(&take,path)&&at_take_load(&loaded,path));
    am_render_dispose(&render); /*The following player takes exclusive ownership. */
    CHECK(at_player_init(&player,&engine,&loaded,channels));
    for(at=0;at<FRAMES;at+=n) {
        n=block(at,349);
#ifndef LM_LEGACY
        CHECK(at_player_process_layers(&player,out,n,NULL,layers)==n);
#else
        CHECK(at_player_process(&player,out,n,NULL)==n);
#endif
        CHECK(!memcmp(out,reference+(size_t)at*channels,n*channels*sizeof(float)));
#ifndef LM_LEGACY
        if(channels==2){LmListen monitor;int selected=1+(int)(at/48000)%LM_LAYERS;CHECK(lm_listen_init(&monitor,selected));memcpy(heard,out,n*2*sizeof(float));CHECK(lm_listen_process(&monitor,heard,layers,n));
            for(unsigned j=0;j<n;++j)for(int cc=0;cc<2;++cc)CHECK(heard[2*j+cc]==layers[j*LM_SAMPLES+2*(selected-1)+cc]);}
#endif
    }
    CHECK(at_player_verified(&player));
#ifndef LM_LEGACY
    CHECK(maximum_error<2e-7&&energy[LM_DNA]>0&&energy[LM_DETAIL]>0&&energy[LM_EVENTS]>0&&energy[LM_AUX]>0);
    CHECK(energy[LM_OTHER]==0);CHECK(!fclose(stem));stem=NULL;
#endif
    snprintf(path,sizeof path,"%s/%s_report.json",root,tag);report=vsl_fopen(path,"wb");CHECK(report);
    fprintf(report,"{\"result\":\"passed\",\"frames\":%u,\"channels\":%d,\"fine_idle\":%d,\"audio_hash\":\"%016llx\",\"source_hash\":\"%016llx\",\"render_id\":\"%s\",\"peak\":%.17g,\"maximum_stem_sum_error\":%.17g,\"layer_energy\":[",
        FRAMES,channels,fine,(unsigned long long)ah,(unsigned long long)sh,at_render_id(),peak,maximum_error);
    for(int k=0;k<6;++k)fprintf(report,"%s%.17g",k?",":"",energy[k]);fputs("]}\n",report);
    CHECK(!fclose(report));report=NULL;ok=1;printf("PASS canonical %s, audio=%016llx source=%016llx error=%.3g\n",tag,(unsigned long long)ah,(unsigned long long)sh,maximum_error);
done:
    if(wave)fclose(wave);if(trace)fclose(trace);if(stem)fclose(stem);if(report)fclose(report);
    am_render_dispose(&render);at_player_dispose(&player);at_take_free(&take);at_take_free(&loaded);free(reference);return ok;
}
int main(int argc,char **argv) {
    if(argc!=2||!fid_models_load(&idle)||!fr_models_load(&moving))return 2;
    for(int fine=0;fine<=1;++fine)for(int ch=2;ch<=12;ch+=10)if(!run(argv[1],fine,ch))return 3;
    return 0;
}
