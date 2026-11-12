#define _CRT_SECURE_NO_WARNINGS
#include "atlas_drive/render.h"
#include "core/engine.h"
#include "profiles/lifecycle.h"
#include "io/file.h"
#include "io/wav.h"
#include <errno.h>
#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#define BLOCK 240
#define STEMS 7
static SdProfile model;static StProfile starter;static CbProfile catch_profile;
static SrProfile detail;static SaBank bank;static RaBank details;
static AdRender render;static VslEngine engine;
static float mix[BLOCK*12],raw[BLOCK*2],dna[BLOCK*2],start[BLOCK*2],delta[BLOCK*2];
static float residual_raw[BLOCK*2],residual[BLOCK*2];static AdTelemetry trace[BLOCK];
int main(int argc,char **argv) {
    const SdProfile *models[1]={&model};const SrProfile *detail_models[1]={&detail};
    AdConfig config={&bank,48271,VSL_V10,2,1./120,DS_OBSERVE_MID,DS_ROUTE_PAIR};
    AdControl control={0};AdCapture cap={0};VslWavWriter wav[STEMS]={{0}};
    const char *suffix[STEMS]={"mix","raw","dna","startup","catch_bloom","residual_raw","residual"};
    float *buffers[STEMS]={mix,raw,dna,start,delta,residual_raw,residual};
    FILE *file,*csv=NULL;unsigned n,i,j,opened=0,frames,mask=0;
    double amount,peak=0;int channels,ok=0,hold;uint64_t seed;char extra,*end;
    char paths[STEMS][4096],csv_path[4096];
    if(argc!=10||sscanf(argv[6],"%lf %c",&amount,&extra)!=1||!isfinite(amount)||amount<0||amount>1||
       sscanf(argv[7],"%d %c",&channels,&extra)!=1||(channels!=2&&channels!=12)||
       (strcmp(argv[8],"starts")&&strcmp(argv[8],"hold"))) {
        fputs("usage: startup_detail_probe A.model early.start bloom.cb detail.residual PREFIX amount0..1 channels2|12 starts|hold SEED\n",stderr);return 1;
    }
    errno=0;seed=strtoull(argv[9],&end,10);
    if(end==argv[9]||*end||argv[9][0]=='-'||errno||!seed)return 1;
    hold=!strcmp(argv[8],"hold");frames=(hold?10u:6u)*48000;
    if(!sd_profile_load(argv[1],&model)||!sa_bank_init(&bank,models,1,0))return 2;
    file=vsl_fopen(argv[2],"rb");if(!file)return 2;i=st_profile_read(file,&starter);if(fclose(file)||!i)return 2;
    file=vsl_fopen(argv[3],"rb");if(!file)return 2;i=cb_profile_read(file,&catch_profile);if(fclose(file)||!i)return 2;
    file=vsl_fopen(argv[4],"rb");if(!file)return 2;i=sr_profile_read(file,&detail);if(fclose(file)||!i)return 2;
    if(!ra_bank_init(&details,detail_models,&model.base_hz,1))return 2;
    config.channels=channels;config.seed=seed;config.startup_profile=&starter;config.catch_profile=&catch_profile;
    config.residual_bank=&details;config.scene_mode=AD_SCENE_STEREO_BED;
    config.root_per_rpm=model.base_hz/vsl_profile(VSL_V10)->idle_rpm;
    control.drive.mode=VSL_BENCH;control.drive.rpm=vsl_profile(VSL_V10)->idle_rpm;
    control.mix.gain=.25;control.mix.detail=1;control.mix.width=1;control.mix.spatial=1;
    control.mix.startup_gain=.5;control.mix.catch_gain=.5;control.mix.residual_gain=amount;
    cap.dna_raw=raw;cap.dna=dna;cap.startup=start;cap.catch_bloom=delta;
    cap.residual_raw=residual_raw;cap.residual=residual;cap.telemetry=trace;
    if(!ad_render_init(&render,&engine,&config,&control))return 2;
    for(i=0;i<STEMS;++i) {
        if(snprintf(paths[i],sizeof paths[i],"%s_%s.wav",argv[5],suffix[i])>=(int)sizeof paths[i])return 3;
        file=vsl_fopen(paths[i],"rb");if(file){fclose(file);return 3;}
    }
    if(snprintf(csv_path,sizeof csv_path,"%s_trace.csv",argv[5])>=(int)sizeof csv_path)return 3;
    file=vsl_fopen(csv_path,"rb");if(file){fclose(file);return 3;}
    for(i=0;i<STEMS;++i){if(!vsl_wav_begin_float(wav+i,paths[i],48000,i?2:channels))goto done;++opened;}
    csv=vsl_fopen(csv_path,"wb");if(!csv)goto done;
    fputs("frame,lifecycle,rpm,root_hz,envelope,start_events,catch_progress,bloom_envelope\n",csv);
    for(n=0;n<frames;n+=BLOCK) {
        double t=n/48000.,u=0;
        control.drive.ignition=hold?t>=.05:(t>=.05&&t<2.25)||(t>=3&&t<5.4);
        control.drive.start_id=(!hold&&t>=3.2)?2:t>=.15?1:0;
        if(!ad_render_set(&render,&control)||!ad_render_process(&render,mix,BLOCK,&cap))goto done;
        if(engine.drive.lifecycle==VSL_CATCH) {
            const VslLifecycleProfile *lp=vsl_lifecycle_profile(config.profile);
            u=engine.drive.life_seconds/(lp->catch_rise_seconds+lp->catch_settle_seconds);
        }
        fprintf(csv,"%u,%d,%.17g,%.17g,%.17g,%d,%.17g,%.17g\n",n,trace[0].lifecycle,trace[0].rpm,
            trace[0].root_hz,trace[0].envelope,engine.drive.start_events,u,render.catch_bloom.envelope);
        mask|=1u<<trace[0].lifecycle;
        for(j=0;j<BLOCK*(unsigned)channels;++j){if(!isfinite(mix[j]))goto done;peak=fmax(peak,fabs(mix[j]));}
        for(i=0;i<STEMS;++i)if(!vsl_wav_write(wav+i,buffers[i],BLOCK))goto done;
    }
    if(ferror(csv)||engine.drive.start_events!=(hold?1u:2u)||(!hold&&mask!=63))goto done;ok=1;
done:
    if(csv&&fclose(csv))ok=0;for(i=0;i<opened;++i)if(!vsl_wav_end(wav+i))ok=0;
    if(ok)printf("frames=%u channels=%d starts=%d lifecycle_mask=%u peak=%.17g\n",frames,channels,engine.drive.start_events,mask,peak);
    return ok?0:4;
}
