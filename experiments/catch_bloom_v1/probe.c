#define _CRT_SECURE_NO_WARNINGS
#include "atlas_drive/render.h"
#include "catch_bloom/voice.h"
#include "core/engine.h"
#include "profiles/lifecycle.h"
#include "io/file.h"
#include "io/wav.h"
#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#define BLOCK 240
static SdProfile model;
static StProfile starter;
static SaBank bank;
static AdRender render;
static VslEngine engine;
static CbVoice bloom;
static float mix[BLOCK*12],base[BLOCK*12],raw[BLOCK*2],dna[BLOCK*2],start[BLOCK*2],delta[BLOCK*2];
static double input[BLOCK*2],added[BLOCK*2];
static AdTelemetry trace[BLOCK];
int main(int argc,char **argv) {
    const SdProfile *models[1]={&model};
    AdConfig config={&bank,48271,VSL_V10,2,1./120,DS_OBSERVE_MID,DS_ROUTE_PAIR};
    AdControl control={0};AdCapture cap={0};CbProfile profile;
    VslWavWriter wav[6]={{0}};
    const char *suffix[6]={"mix","base","raw","dna","startup","bloom"};
    float *buffers[6]={mix,base,raw,dna,start,delta};
    FILE *file,*csv=NULL;unsigned n,i,j,opened=0,frames=6*48000,mask=0;
    double amount,peak=0;int channels,ok=0;char extra,paths[6][4096],csv_path[4096];
    if(argc!=7||sscanf(argv[5],"%lf %c",&amount,&extra)!=1||!isfinite(amount)||amount<0||amount>1||
       sscanf(argv[6],"%d %c",&channels,&extra)!=1||(channels!=2&&channels!=12)) {
        fputs("usage: catch_bloom_probe A_cabin.model early.start bloom.cb OUT_PREFIX amount0..1 channels2|12\n",stderr);return 1;
    }
    if(!sd_profile_load(argv[1],&model)||!sa_bank_init(&bank,models,1,0))return 2;
    file=vsl_fopen(argv[2],"rb");if(!file)return 2;i=st_profile_read(file,&starter);if(fclose(file)||!i)return 2;
    file=vsl_fopen(argv[3],"rb");if(!file)return 2;i=cb_profile_read(file,&profile);if(fclose(file)||!i)return 2;
    if(!cb_voice_init(&bloom,&profile,amount))return 2;
    config.channels=channels;config.startup_profile=&starter;config.scene_mode=AD_SCENE_STEREO_BED;
    /* Preserve the earlier preview mapping, not an ECU/RPM calibration. */
    config.root_per_rpm=model.base_hz/vsl_profile(VSL_V10)->idle_rpm;
    control.drive.mode=VSL_BENCH;control.drive.rpm=vsl_profile(VSL_V10)->idle_rpm;
    control.mix.gain=.25;control.mix.detail=1;control.mix.width=1;
    control.mix.startup_gain=.5;control.mix.spatial=1;
    cap.dna_raw=raw;cap.dna=dna;cap.startup=start;cap.telemetry=trace;
    if(!ad_render_init(&render,&engine,&config,&control))return 2;
    for(i=0;i<6;++i) {
        if(snprintf(paths[i],sizeof paths[i],"%s_%s.wav",argv[4],suffix[i])>=(int)sizeof paths[i])return 3;
        file=vsl_fopen(paths[i],"rb");if(file){fclose(file);return 3;}
    }
    if(snprintf(csv_path,sizeof csv_path,"%s_trace.csv",argv[4])>=(int)sizeof csv_path)return 3;
    file=vsl_fopen(csv_path,"rb");if(file){fclose(file);return 3;}
    for(i=0;i<6;++i){if(!vsl_wav_begin_float(wav+i,paths[i],48000,i<2?channels:2))goto done;++opened;}
    csv=vsl_fopen(csv_path,"wb");if(!csv)goto done;
    fputs("frame,lifecycle,rpm,root_hz,envelope,start_events,catch_progress,bloom_envelope\n",csv);
    for(n=0;n<frames;n+=BLOCK) {
        double t=n/48000.,u=0;int gate;
        control.drive.ignition=(t>=.05&&t<2.25)||(t>=3&&t<5.4);
        control.drive.start_id=t>=3.2?2:t>=.15?1:0;
        if(!ad_render_set(&render,&control)||!ad_render_process(&render,base,BLOCK,&cap))goto done;
        /* ad_render advances the only controller at the block's first frame.
           Read that block's state; do not step a second driver or infer RPM. */
        if(trace[0].lifecycle!=engine.drive.lifecycle)return 5;
        gate=engine.drive.lifecycle==VSL_CATCH;
        if(gate) {
            const VslLifecycleProfile *lp=vsl_lifecycle_profile(config.profile);
            u=fmin(1,engine.drive.life_seconds/(lp->catch_rise_seconds+lp->catch_settle_seconds));
        }
        if(!cb_voice_set(&bloom,gate,u,amount))goto done;
        for(j=0;j<BLOCK*2;++j)input[j]=dna[j];
        if(!cb_voice_process(&bloom,input,added,BLOCK))goto done;
        memcpy(mix,base,sizeof(float)*BLOCK*channels);
        for(j=0;j<BLOCK;++j)for(i=0;i<2;++i) {
            delta[2*j+i]=(float)added[2*j+i];
            if(added[2*j+i]!=0)mix[j*channels+i]=(float)(base[j*channels+i]+added[2*j+i]*render.gain);
        }
        fprintf(csv,"%u,%d,%.17g,%.17g,%.17g,%d,%.17g,%.17g\n",n,trace[0].lifecycle,trace[0].rpm,
            trace[0].root_hz,trace[0].envelope,engine.drive.start_events,u,bloom.envelope);
        mask|=1u<<trace[0].lifecycle;
        for(j=0;j<BLOCK*(unsigned)channels;++j){if(!isfinite(mix[j]))goto done;peak=fmax(peak,fabs(mix[j]));}
        for(i=0;i<6;++i)if(!vsl_wav_write(wav+i,buffers[i],BLOCK))goto done;
    }
    if(ferror(csv)||engine.drive.start_events!=2||mask!=63)goto done;
    ok=1;
done:
    if(csv&&fclose(csv))ok=0;
    for(i=0;i<opened;++i)if(!vsl_wav_end(wav+i))ok=0;
    if(ok)printf("frames=%u channels=%d starts=%d lifecycle_mask=%u peak=%.17g\n",frames,channels,engine.drive.start_events,mask,peak);
    return ok?0:4;
}
