#define _CRT_SECURE_NO_WARNINGS
#include "models.h"
#include "atlas_monitor/render.h"
#include "atlas_take/take.h"
#include "atlas_take_io/file.h"
#include "core/engine.h"
#include "drive/scenarios.h"
#include "io/file.h"
#include "io/wav.h"
#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#define CHECK(x) do{if(!(x)){fprintf(stderr,"stationary%d: %s\n",__LINE__,#x);goto done;}}while(0)
static SbmModels models;static AmRender render;static VslEngine engine;
static float raw[480],dna[480],body[480],residual[480],resonant[480],lowraw[480],low[480];
static float aux[240*VSL_OBJECTS],events[240],startup[480],catching[480],layers[240*LM_SAMPLES];
static AdTelemetry telemetry[240];
static void control(int scenario,unsigned at,AdControl *c) {
    VslParams p=vsl_default_params(VSL_V10);
    vsl_scenario_apply(scenario,at/48000.,&p);
    c->drive.mode=p.drive_mode;c->drive.ignition=p.ignition;c->drive.start_id=p.start_id;
    c->drive.rpm=p.rpm;c->drive.load=p.load;c->drive.throttle=p.throttle;c->drive.brake=p.brake;
    c->drive.gear=p.gear;c->drive.automatic=p.auto_gear;c->drive.backfire=p.backfire;
}
int main(int argc,char **argv) {
    AdConfig cfg={0};AdControl c={0};AdCapture cap={0};AtTake take={0};VslWavWriter wav={0},stem={0};
    FILE *trace=NULL,*report=NULL,*buses=NULL;unsigned frames,block,at,n,active=0,states[8]={0};
    int variant,channels,scenario,ok=0;char path[4096];float out[240*12];
    uint64_t ah=AT_HASH_INITIAL,sh=AT_HASH_INITIAL;double peak=0,energy=0;
    if(argc!=6)return 2;variant=atoi(argv[2]);channels=atoi(argv[4]);block=(unsigned)atoi(argv[5]);
    scenario=vsl_scenario_id(argv[3]);frames=!strcmp(argv[3],"neutral")?576000u:768000u;
    if(variant<0||variant>2||(channels!=2&&channels!=12)||!block||block>240||scenario<0)return 2;
    CHECK(sbm_models_load(&models));
    cfg.bank=&models.bank;cfg.seed=48271;cfg.profile=VSL_V10;cfg.channels=channels;
    cfg.root_per_rpm=1./120;cfg.scene_mode=AD_SCENE_STEREO_BED;
    if(variant){cfg.resonant_bank=&models.resonance;cfg.recipe_bank=&models.recipe;}
    c.mix.gain=.25;c.mix.width=c.mix.detail=1;c.mix.spatial=channels==12;
    c.mix.resonant_gain=variant==2;control(scenario,0,&c);
    cap.dna_raw=raw;cap.dna=dna;cap.body=body;cap.residual=residual;cap.events=events;cap.aux_objects=aux;
    cap.startup=startup;cap.catch_bloom=catching;cap.resonant=resonant;cap.coherent_low_raw=lowraw;cap.coherent_low=low;
    cap.telemetry=telemetry;cap.layers=layers;
    CHECK(at_take_allocate(&take,4096)&&at_take_begin(&take,&cfg,&c)&&am_render_init(&render,&engine,&cfg,&c));
    snprintf(path,sizeof path,"%s.wav",argv[1]);CHECK(vsl_wav_begin_float(&wav,path,48000,channels));
    snprintf(path,sizeof path,"%s_detail.wav",argv[1]);CHECK(vsl_wav_begin_float(&stem,path,48000,2));
    snprintf(path,sizeof path,"%s_layers.f32",argv[1]);buses=vsl_fopen(path,"wb");CHECK(buses);
    snprintf(path,sizeof path,"%s.csv",argv[1]);trace=vsl_fopen(path,"wb");CHECK(trace);
    fputs("frame,rpm,speed,load,gear,lifecycle,operating,fuel,root_hz,detail_support,shifts,overruns\n",trace);
    for(at=0;at<frames;at+=n) {
        n=240-at%240;if(n>block)n=block;if(n>frames-at)n=frames-at;
        if(at%240==0)control(scenario,at,&c);
        CHECK(at_take_event(&take,at,&c)&&am_render_set(&render,&c));
        CHECK(am_render_process(&render,out,n,0,&cap));
        ah=at_hash_samples(ah,out,n*channels);sh=at_hash_sources(sh,&cap,n);
        CHECK(at_take_commit(&take,n,ah,sh)&&vsl_wav_write(&wav,out,n)&&vsl_wav_write(&stem,resonant,n));
        CHECK(fwrite(layers,sizeof(float),n*LM_SAMPLES,buses)==n*LM_SAMPLES);
        for(unsigned j=0;j<n;++j) {
            AdTelemetry *t=telemetry+j;
            if(t->resonant_support>0)++active;if(t->operating>=0&&t->operating<8)++states[t->operating];
            if((at+j)%240==0)fprintf(trace,"%u,%.17g,%.17g,%.17g,%d,%d,%d,%d,%.17g,%.17g,%u,%u\n",
                at+j,t->rpm,t->speed,t->load,t->gear,t->lifecycle,t->operating,t->fuel_mode,t->root_hz,t->resonant_support,t->shifts,t->overruns);
            for(int k=0;k<channels;++k){double x=out[j*channels+k];CHECK(isfinite(x)&&fabs(x)<.95);peak=fmax(peak,fabs(x));energy+=x*x;}
        }
    }
    CHECK(energy>0);am_render_dispose(&render);at_take_finish(&take);
    CHECK(vsl_wav_end(&wav)&&vsl_wav_end(&stem));
    CHECK(!fclose(trace));trace=NULL;CHECK(!fclose(buses));buses=NULL;
    snprintf(path,sizeof path,"%s.vslrun",argv[1]);CHECK(at_take_save(&take,path));
    snprintf(path,sizeof path,"%s.json",argv[1]);report=vsl_fopen(path,"wb");CHECK(report);
    fprintf(report,"{\"result\":\"pass\",\"frames\":%u,\"variant\":%d,\"channels\":%d,\"block\":%u,\"audio_hash\":\"%016llx\",\"source_hash\":\"%016llx\",\"render_id\":\"%s\",\"detail_supported_frames\":%u,\"peak\":%.17g,\"state_frames\":[",
        frames,variant,channels,block,(unsigned long long)ah,(unsigned long long)sh,at_render_id(),active,peak);
    for(unsigned j=0;j<8;++j)fprintf(report,"%s%u",j?",":"",states[j]);fputs("]}\n",report);ok=1;
done:
    if(report&&fclose(report))ok=0;if(trace)fclose(trace);if(buses)fclose(buses);
    if(wav.file)vsl_wav_end(&wav);if(stem.file)vsl_wav_end(&stem);
    am_render_dispose(&render);at_take_free(&take);return ok?0:3;
}
