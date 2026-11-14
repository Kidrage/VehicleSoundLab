#define _CRT_SECURE_NO_WARNINGS
#include "timing.h"
#include "../fine_idle_drive_v1/models.h"
#include "../full_recipe_drive_v1/models.h"
#include "../atlas_monitor_v1/audio.h"
#include "drive/scenarios.h"
#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
static FrModels moving;
static FidModels idle;
static AdRender render;
static VslEngine engine;
static uint64_t hash(uint64_t h,const void *ptr,size_t n){const unsigned char *p=ptr;for(size_t i=0;i<n;++i){h^=p[i];h*=UINT64_C(1099511628211);}return h;}
int main(int argc,char **argv){
    AdConfig cfg={0};AdControl c;VslParams params=vsl_default_params(VSL_V10);
    float pcm[512*2];unsigned at,frames=12*48000,blocks=0,exceeded=0;double total=0,max=0;
    uint64_t output_hash=UINT64_C(14695981039346656037),frequency=sp_frequency();FILE *trace,*raw;char raw_path[4096];
    if(argc!=3||(strcmp(argv[1],"idle")&&strcmp(argv[1],"drive")))return 2;
    trace=fopen(argv[2],"rb");if(trace){fclose(trace);return 2;}trace=fopen(argv[2],"wb");if(!trace)return 2;
    if(snprintf(raw_path,sizeof raw_path,"%s.f32",argv[2])>=sizeof raw_path)return 2;
    raw=fopen(raw_path,"rb");if(raw){fclose(raw);return 2;}raw=fopen(raw_path,"wb");if(!raw)return 2;
    if(!fr_models_load(&moving)||!fid_models_load(&idle))return 3;
    cfg.bank=&moving.bank;cfg.seed=48271;cfg.profile=VSL_V10;cfg.channels=2;cfg.root_per_rpm=1./120;
    cfg.scene_mode=AD_SCENE_STEREO_BED;cfg.resonant_bank=&moving.resonance;cfg.recipe_bank=&moving.recipe;cfg.fine_idle_profile=&idle.idle;
    c=am_default_control();c.drive.mode=VSL_BENCH;c.drive.ignition=1;c.drive.start_id=1;c.drive.rpm=850;c.drive.load=0;
    c.mix.idle_motion=.5;c.mix.idle_detail=1;c.mix.width=c.mix.resonant_gain=c.mix.coherent_low_gain=c.mix.idle_mix=1;
    if(!ad_render_init(&render,&engine,&cfg,&c))return 3;
    sp_reset();for(unsigned i=0;i<100000;++i){uint64_t t=sp_begin();sp_end(SP_EMPTY,t);}
    fputs("frame,frames,elapsed_ms,rpm,operating,idle_weight\n",trace);
    for(at=0;at<frames;){unsigned n=frames-at>512?512:frames-at;AdTelemetry telemetry[512];AdCapture capture={0};uint64_t begin;double elapsed;
        if(!strcmp(argv[1],"drive")){
            vsl_scenario_apply(VSL_SCENARIO_SHIFTS,at/48000.,&params);
            c.drive=(AdInput){params.drive_mode,params.ignition,params.start_id,params.gear,params.auto_gear,params.backfire,params.rpm,params.load,params.throttle,params.brake};
            if(!ad_render_set(&render,&c))return 3;
        }
        capture.telemetry=telemetry;begin=sp_begin();if(!ad_render_process(&render,pcm,n,&capture))return 3;
        elapsed=(sp_begin()-begin)/(double)frequency;total+=elapsed;if(elapsed>max)max=elapsed;if(elapsed>n/48000.)++exceeded;
        for(unsigned j=0;j<2*n;++j)if(!isfinite(pcm[j]))return 3;
        output_hash=hash(output_hash,pcm,n*2*sizeof *pcm);
        if(fwrite(pcm,sizeof *pcm,n*2,raw)!=n*2)return 3;
        fprintf(trace,"%u,%u,%.17g,%.17g,%d,%.17g\n",at,n,elapsed*1000,engine.drive.rpm,engine.drive.operating,telemetry[n-1].idle_weight);
        at+=n;++blocks;
    }
    if(fclose(trace)||fclose(raw))return 3;ad_render_dispose(&render);
    printf("{\"case\":\"%s\",\"frames\":%u,\"blocks\":%u,\"total_seconds\":%.12g,\"max_ms\":%.12g,\"budget_exceedances\":%u,\"output_hash\":\"%016llx\",\"metrics\":[",argv[1],frames,blocks,total,max*1000,exceeded,(unsigned long long)output_hash);
    for(unsigned i=0;i<SP_COUNT;++i)printf("%s{\"stage\":\"%s\",\"calls\":%llu,\"seconds\":%.12g}",i?",":"",sp_names[i],(unsigned long long)sp_metrics[i].calls,sp_metrics[i].ticks/(double)frequency);
    puts("]}");return 0;
}
