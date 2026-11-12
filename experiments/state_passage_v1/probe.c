#define _CRT_SECURE_NO_WARNINGS
#include "trajectory.h"
#include "dna_atlas/voice.h"
#include "io/wav.h"
#include <math.h>
#include <stdio.h>
#include <stdlib.h>

static SpTrajectory path;
static SdProfile models[SA_MAX_ANCHORS];
static SaBank bank;
static SaVoice voice;

int main(int argc,char **argv) {
    const SdProfile *profiles[SA_MAX_ANCHORS];
    VslWavWriter wav; FILE *trace;
    unsigned i,n,frames,used=0; double detail,peak=0;
    unsigned long long seed; unsigned alignment; char extra;
    float block[480*2];
    if(argc<8||argc>7+SA_MAX_ANCHORS||
       sscanf(argv[4],"%lf %c",&detail,&extra)!=1||!isfinite(detail)||detail<0||detail>1||
       sscanf(argv[5],"%llu %c",&seed,&extra)!=1||
       sscanf(argv[6],"%u %c",&alignment,&extra)!=1||alignment>32) {
        fputs("trajectory.txt output.wav trace.csv detail0..1 seed align0..32 model [model...]\n",stderr);return 1;
    }
    if(!sp_trajectory_load(&path,argv[1]))return 2;
    for(i=7;i<(unsigned)argc;++i) {
        if(!sd_profile_load(argv[i],&models[i-7]))return 3;
        profiles[i-7]=&models[i-7];
    }
    if(!sa_bank_init(&bank,profiles,(unsigned)argc-7,alignment)||
       !sa_voice_init(&voice,&bank,seed,path.point[0].root_hz,detail,1))return 4;
    trace=fopen(argv[3],"wb");if(!trace)return 5;
    if(!vsl_wav_begin_float(&wav,argv[2],48000,2)){fclose(trace);return 5;}
    fputs("frame,target_acoustic_hz,actual_acoustic_hz,lower,upper,blend,coverage\n",trace);
    frames=path.point[path.count-1].frame;
    for(n=0;n<frames;++n) {
        double hz,out[2];
        if(!sp_trajectory_value(&path,n,&hz)||!sa_voice_set(&voice,hz,detail,1))return 6;
        sa_voice_tick(&voice,out);
        if(n%240==0||n+1==frames)fprintf(trace,"%u,%.17g,%.17g,%u,%u,%.17g,%d\n",
            n,hz,voice.root_hz,voice.lower,voice.upper,voice.blend,voice.coverage);
        for(i=0;i<2;++i) {
            if(!isfinite(out[i]))return 7;
            if(fabs(out[i])>peak)peak=fabs(out[i]);
            block[used*2+i]=(float)out[i];
        }
        if(++used==480||n+1==frames) {
            if(!vsl_wav_write(&wav,block,used))return 8;
            used=0;
        }
    }
    if(ferror(trace)||fclose(trace)||!vsl_wav_end(&wav))return 8;
    printf("frames=%u peak=%.17g anchors=%u follow_ms=18 source_only=1\n",frames,peak,bank.count);
    return 0;
}
