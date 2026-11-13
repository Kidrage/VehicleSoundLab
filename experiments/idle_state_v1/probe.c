#define _CRT_SECURE_NO_WARNINGS
#include "source.h"
#include "atlas_drive/render.h"
#include "../full_recipe_drive_v1/models.h"
#include "io/wav.h"
#include "io/file.h"
#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#define BLOCK 240
#define FILES 6
static MiModels idle;static FrModels moving;static IsSource source;
static AdRender render;static VslEngine engine;
static MlFrame stages[BLOCK];static AdTelemetry telemetry[BLOCK];
static float audio[FILES][2*BLOCK],observation[2*BLOCK],added[2*BLOCK];
static const char *names[FILES]={"mix","modal_raw","detail_raw","idle_raw","idle_added","retained_old"};
int main(int argc,char **argv) {
    AdConfig cfg={0};AdControl p={0};AdCapture cap={0};VslWavWriter wav[FILES];FILE *trace;
    char path[2048],extra;unsigned at,n,i,c,frames=384000;int enabled;unsigned long long seed;
    double peak=0;
    if(argc!=4||sscanf(argv[2],"%d %c",&enabled,&extra)!=1||(enabled!=0&&enabled!=1)||
       sscanf(argv[3],"%llu %c",&seed,&extra)!=1)return 1;
    if(!mi_models_load(&idle,"experiments/modal_idle_v1/F2_fixed_idle.msource","experiments/modal_idle_v1/F2_fixed_idle.rdetail")||
       !fr_models_load(&moving)||!is_source_init(&source,&idle,(uint64_t)seed,enabled))return 2;
    cfg.bank=&moving.bank;cfg.seed=48271;cfg.profile=VSL_V10;cfg.channels=2;cfg.root_per_rpm=1./120;
    cfg.scene_mode=AD_SCENE_STEREO_BED;cfg.resonant_bank=&moving.resonance;cfg.recipe_bank=&moving.recipe;cfg.source_processor=&source.processor;
    p.drive.mode=VSL_BENCH;p.drive.ignition=1;p.drive.start_id=1;p.drive.rpm=850;
    p.mix.gain=.25;p.mix.detail=p.mix.width=p.mix.resonant_gain=p.mix.coherent_low_gain=1;
    if(!ad_render_init(&render,&engine,&cfg,&p))return 3;
    for(i=0;i<FILES;++i){snprintf(path,sizeof path,"%s_%s.wav",argv[1],names[i]);if(!vsl_wav_begin_float(wav+i,path,48000,2))return 4;}
    snprintf(path,sizeof path,"%s_trace.f64",argv[1]);trace=vsl_fopen(path,"wb");if(!trace)return 4;
    cap.source_added=added;cap.observation=observation;cap.telemetry=telemetry;
    source.capture=stages;source.capture_capacity=BLOCK;
    for(at=0;at<frames;at+=n) {
        n=frames-at;if(n>BLOCK)n=BLOCK;
        if(at==96000){p.drive.rpm=2200;p.drive.load=.6;if(!ad_render_set(&render,&p))return 5;}
        if(at==192000){p.drive.rpm=850;p.drive.load=0;if(!ad_render_set(&render,&p))return 5;}
        if(at==288000){p.drive.ignition=0;if(!ad_render_set(&render,&p))return 5;}
        source.capture_count=0;
        if(!ad_render_process(&render,audio[0],n,&cap)||source.capture_count!=n)return 6;
        for(i=0;i<n;++i) {
            double row[6]={telemetry[i].rpm,telemetry[i].lifecycle,telemetry[i].operating,
                           telemetry[i].envelope,stages[i].weight,stages[i].keep};
            if(fwrite(row,sizeof(double),6,trace)!=6)return 7;
            for(c=0;c<2;++c) {
                unsigned k=2*i+c;
                audio[1][k]=(float)stages[i].modal[c];audio[2][k]=(float)stages[i].detail[c];
                audio[3][k]=(float)stages[i].raw[c];audio[4][k]=added[k];
                audio[5][k]=observation[k]-added[k];
                if(fabs(audio[0][k])>peak)peak=fabs(audio[0][k]);
            }
        }
        for(i=0;i<FILES;++i)if(!vsl_wav_write(wav+i,audio[i],n))return 7;
    }
    for(i=0;i<FILES;++i)if(!vsl_wav_end(wav+i))return 7;
    if(fclose(trace))return 7;
    printf("frames=%u seed=%llu enabled=%d peak=%.17g gate_samples=%llu modal_ratio=1 level_gain=%.17g calibrated_RPM=0\n",frames,seed,enabled,peak,source.enabled_samples,source.profile.level_gain);
    return 0;
}
