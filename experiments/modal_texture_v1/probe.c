#define _CRT_SECURE_NO_WARNINGS
#include "modal_source/io.h"
#include "modal_texture/io.h"
#include "modal_texture/envelope.h"
#include "modal_source/voice.h"
#include "io/file.h"
#include "io/wav.h"
#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
static MsProfile source;
static MtProfile texture;
static MsVoice voice;
static MtEnvelope envelope;
int main(int argc,char **argv) {
    unsigned frames,n,used=0,c;unsigned long long seed;double seconds,ratio,amount,peak=0;
    VslWavWriter writer;FILE *dump=NULL;char extra;float block[480*2];
    if((argc!=8&&argc!=9)||sscanf(argv[4],"%lf %c",&seconds,&extra)!=1||!isfinite(seconds)||seconds<=0||seconds>120||
       sscanf(argv[5],"%llu %c",&seed,&extra)!=1||sscanf(argv[6],"%lf %c",&ratio,&extra)!=1||
       sscanf(argv[7],"%lf %c",&amount,&extra)!=1) {
        fputs("source.msource texture.mtexture output.wav seconds seed ratio amount [gains.f64]\n",stderr);return 1;
    }
    if(!ms_profile_load(argv[1],&source)||!mt_profile_load(argv[2],&texture)||source.count!=texture.count||
       !ms_voice_init(&voice,&source,ratio,1)||!mt_envelope_init(&envelope,&texture,(uint64_t)seed,amount))return 2;
    if(!vsl_wav_begin_float(&writer,argv[3],48000,2))return 3;
    if(argc==9&&(dump=vsl_fopen(argv[8],"wb"))==NULL)return 4;
    frames=(unsigned)floor(seconds*48000+.5);
    for(n=0;n<frames;++n) {
        double gains[MT_MAX_MODES],out[2];
        if(!mt_envelope_tick(&envelope,gains)||!ms_voice_tick_gains(&voice,amount==0?NULL:gains,out))return 5;
        if(dump&&fwrite(gains,sizeof(double),texture.count,dump)!=texture.count)return 6;
        for(c=0;c<2;++c) {
            if(!isfinite(out[c])||fabs(out[c])>3.4e38)return 7;
            if(fabs(out[c])>peak)peak=fabs(out[c]);block[2*used+c]=(float)out[c];
        }
        if(++used==480||n+1==frames){if(!vsl_wav_write(&writer,block,used))return 8;used=0;}
    }
    if(!vsl_wav_end(&writer)||(dump&&fclose(dump)))return 9;
    printf("frames=%u modes=%u peak=%.17g amount=%.17g phase_FM=0 room=0\n",frames,source.count,peak,amount);return 0;
}
