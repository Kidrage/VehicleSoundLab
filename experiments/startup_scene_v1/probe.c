#define _CRT_SECURE_NO_WARNINGS
#include "atlas_drive/render.h"
#include "core/engine.h"
#include "io/file.h"
#include "io/wav.h"
#include <math.h>
#include <stdio.h>
#include <stdlib.h>

#define BLOCK 240
static SdProfile model;
static StProfile starter;
static SaBank bank;
static AdRender render;
static VslEngine engine;
static float output[BLOCK*12],raw[BLOCK*2],dna[BLOCK*2],start[BLOCK*2];
static AdTelemetry trace[BLOCK];

int main(int argc,char **argv) {
    const SdProfile *models[1]={&model};
    AdConfig config={&bank,48271,VSL_V10,2,1./120,DS_OBSERVE_MID,DS_ROUTE_PAIR};
    AdControl control={0};
    AdCapture capture={0};
    VslWavWriter wav[4]={{0}};
    const char *suffix[4]={"mix","raw","dna","startup"};
    float *buffers[4]={output,raw,dna,start};
    FILE *file,*csv=NULL;
    unsigned n,i,j,opened=0,frames=6*48000,phase_mask=0;
    double amount,peak=0;int channels,ok=0;char extra,paths[4][4096],csv_path[4096];
    if(argc!=6||sscanf(argv[4],"%lf %c",&amount,&extra)!=1||!isfinite(amount)||amount<0||amount>1||
        sscanf(argv[5],"%d %c",&channels,&extra)!=1||(channels!=2&&channels!=12)) {
        fputs("usage: startup_scene_probe A_cabin.model early.start OUT_PREFIX startup0..1 channels2|12\n",stderr);return 1;
    }
    if(!sd_profile_load(argv[1],&model)||!sa_bank_init(&bank,models,1,0))return 2;
    file=vsl_fopen(argv[2],"rb");if(!file)return 2;
    i=st_profile_read(file,&starter);if(fclose(file)||!i)return 2;
    config.channels=channels;config.startup_profile=&starter;config.scene_mode=AD_SCENE_STEREO_BED;
    /* Preview mapping only: make the existing idle policy meet this measured
       acoustic anchor. It is not an inferred ECU RPM calibration. */
    config.root_per_rpm=model.base_hz/vsl_profile(VSL_V10)->idle_rpm;
    control.drive.mode=VSL_BENCH;
    control.drive.rpm=vsl_profile(VSL_V10)->idle_rpm;control.drive.load=0;
    control.mix.gain=.25;control.mix.detail=1;control.mix.width=1;
    control.mix.startup_gain=amount;control.mix.spatial=1;
    capture.dna_raw=raw;capture.dna=dna;capture.startup=start;capture.telemetry=trace;
    if(!ad_render_init(&render,&engine,&config,&control))return 2;
    for(i=0;i<4;++i) {
        if(snprintf(paths[i],sizeof paths[i],"%s_%s.wav",argv[3],suffix[i])>=(int)sizeof paths[i])return 3;
        file=vsl_fopen(paths[i],"rb");if(file){fclose(file);return 3;}
    }
    if(snprintf(csv_path,sizeof csv_path,"%s_trace.csv",argv[3])>=(int)sizeof csv_path)return 3;
    file=vsl_fopen(csv_path,"rb");if(file){fclose(file);return 3;}
    for(i=0;i<4;++i){if(!vsl_wav_begin_float(wav+i,paths[i],48000,i?2:channels))goto done;++opened;}
    csv=vsl_fopen(csv_path,"wb");if(!csv)goto done;
    fputs("frame,lifecycle,rpm,root_hz,envelope,start_events\n",csv);
    for(n=0;n<frames;n+=BLOCK) {
        double t=n/48000.;
        control.drive.ignition=(t>=.05&&t<2.25)||(t>=3&&t<5.4);
        control.drive.start_id=t>=3.2?2:t>=.15?1:0;
        if(!ad_render_set(&render,&control)||!ad_render_process(&render,output,BLOCK,&capture))goto done;
        fprintf(csv,"%u,%d,%.17g,%.17g,%.17g,%d\n",n,trace[0].lifecycle,trace[0].rpm,trace[0].root_hz,
            trace[0].envelope,engine.drive.start_events);
        phase_mask|=1u<<trace[0].lifecycle;
        for(j=0;j<BLOCK*(unsigned)channels;++j){if(!isfinite(output[j]))goto done;peak=fmax(peak,fabs(output[j]));}
        for(i=0;i<4;++i)if(!vsl_wav_write(wav+i,buffers[i],BLOCK))goto done;
    }
    if(ferror(csv)||engine.drive.start_events!=2||phase_mask!=63)goto done;
    ok=1;
done:
    if(csv&&fclose(csv))ok=0;
    for(i=0;i<opened;++i)if(!vsl_wav_end(wav+i))ok=0;
    if(ok)printf("frames=%u channels=%d starts=%d lifecycle_mask=%u peak=%.17g root_per_rpm=%.17g\n",
        frames,channels,engine.drive.start_events,phase_mask,peak,config.root_per_rpm);
    return ok?0:4;
}
