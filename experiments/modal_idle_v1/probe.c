#define _CRT_SECURE_NO_WARNINGS
#include "models.h"
#include "modal_source/voice.h"
#include "resonant_detail/voice.h"
#include "io/wav.h"
#include <math.h>
#include <stdio.h>
#include <stdlib.h>
static MiModels models;
static MsVoice modal;
static RdtVoice detail;
int main(int argc,char **argv) {
    unsigned n,frames,used=0,i;unsigned long long seed;double seconds,ratio,amount,peak=0;char extra;
    VslWavWriter writers[3];char path[2048];float block[3][480*2];
    const char *suffix[3]={"modal","detail","mix"};
    if(argc!=8||sscanf(argv[4],"%lf %c",&seconds,&extra)!=1||!isfinite(seconds)||seconds<=0||seconds>120||
       sscanf(argv[5],"%llu %c",&seed,&extra)!=1||
       sscanf(argv[6],"%lf %c",&ratio,&extra)!=1||
       sscanf(argv[7],"%lf %c",&amount,&extra)!=1||!isfinite(amount)||amount<0||amount>1) {
        fputs("modal.msource detail.rdetail output_prefix seconds seed modal_ratio detail0..1\n",stderr);return 1;
    }
    if(!mi_models_load(&models,argv[1],argv[2])||!ms_voice_init(&modal,&models.modal,ratio,1)||
       !rdt_voice_init(&detail,&models.detail,(uint64_t)seed))return 2;
    for(n=0;n<models.detail.warmup_frames;++n){double out[2];if(!rdt_voice_tick(&detail,0,out,NULL))return 3;}
    for(i=0;i<3;++i) {
        int length=snprintf(path,sizeof path,"%s_%s.wav",argv[3],suffix[i]);
        if(length<0||(size_t)length>=sizeof path||!vsl_wav_begin_float(writers+i,path,48000,2))return 4;
    }
    frames=(unsigned)floor(seconds*48000+.5);
    for(n=0;n<frames;++n) {
        double m[2],d[2];unsigned c;
        if(!ms_voice_tick(&modal,m)||!rdt_voice_tick(&detail,0,d,NULL))return 5;
        for(c=0;c<2;++c) {
            double mixed=m[c]+amount*d[c];
            if(!isfinite(mixed))return 6;
            if(fabs(mixed)>peak)peak=fabs(mixed);
            block[0][used*2+c]=(float)m[c];block[1][used*2+c]=(float)(amount*d[c]);block[2][used*2+c]=(float)mixed;
        }
        if(++used==480||n+1==frames) {
            for(i=0;i<3;++i)if(!vsl_wav_write(writers+i,block[i],used))return 7;
            used=0;
        }
    }
    for(i=0;i<3;++i)if(!vsl_wav_end(writers+i))return 7;
    printf("frames=%u modes=%u resonators=%u peak=%.17g modal_ratio=%.17g source_only=1 shared_clock=0 room=0\n",
        frames,models.modal.count,models.detail.count,peak,ratio);
    return 0;
}
