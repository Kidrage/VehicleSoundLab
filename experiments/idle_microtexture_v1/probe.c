#define _CRT_SECURE_NO_WARNINGS
#include "modal_source/io.h"
#include "modal_texture/io.h"
#include "modal_texture/voice.h"
#include "spectral_motion/voice.h"
#include "spectral_texture/io.h"
#include "io/wav.h"
#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#ifdef _WIN32
#include <windows.h>
static double seconds_now(void){LARGE_INTEGER t,f;QueryPerformanceCounter(&t);QueryPerformanceFrequency(&f);return (double)t.QuadPart/(double)f.QuadPart;}
#else
#include <time.h>
static double seconds_now(void){struct timespec t;timespec_get(&t,TIME_UTC);return t.tv_sec+t.tv_nsec*1e-9;}
#endif
static MsProfile source;
static MtProfile amplitude;
static SfProfile fine;
static MsVoice core;
static int order(const void *a,const void *b){double x=*(const double*)a,y=*(const double*)b;return(x>y)-(x<y);}
int main(int argc,char **argv) {
    SpmProfile profile;SpmVoice *detail;VslWavWriter writers[3];char path[2048],extra;
    const char *suffix[]={"core","detail","mix"};float output[3][480*2];
    unsigned frames,start,i,c,chunks=0,overruns=0,chunk_frames,capacity;unsigned long long seed;
    double duration,ratio,amount,init_started,init_seconds,total=0,worst=0,peak=0,*timing;
    if(argc!=11||sscanf(argv[5],"%lf %c",&duration,&extra)!=1||!isfinite(duration)||duration<1./48000||duration>120||
       sscanf(argv[6],"%llu %c",&seed,&extra)!=1||sscanf(argv[7],"%lf %c",&ratio,&extra)!=1||
       sscanf(argv[8],"%lf %c",&amount,&extra)!=1||sscanf(argv[9],"%u %c",&chunk_frames,&extra)!=1||
       !chunk_frames||chunk_frames>480||(strcmp(argv[10],"static")&&strcmp(argv[10],"controls"))) {
        fputs("source.msource amplitude.mtexture fine.sfir prefix seconds seed ratio detail_motion chunk1..480 static|controls\n",stderr);return 1;
    }
    if(!ms_profile_load(argv[1],&source)||!mt_profile_load(argv[2],&amplitude)||!sf_profile_load(argv[3],&fine)||
       !ms_voice_init(&core,&source,ratio,1))return 2;
    if(amplitude.count>fine.count)return 2;
    init_started=seconds_now();memset(&profile,0,sizeof profile);profile.spectral=&fine;profile.motion=&amplitude;
    for(i=0;i<amplitude.count;++i)profile.map[fine.count-amplitude.count+i]=i+1;
    detail=spm_voice_create(&profile,(uint64_t)seed,amount);if(!detail)return 3;
    init_seconds=seconds_now()-init_started;
    frames=(unsigned)floor(duration*48000+.5);capacity=frames/chunk_frames+1;timing=calloc(capacity,sizeof *timing);if(!timing)return 4;
    for(i=0;i<3;++i) {
        int len=snprintf(path,sizeof path,"%s_%s.wav",argv[4],suffix[i]);
        if(len<0||(size_t)len>=sizeof path||!vsl_wav_begin_float(writers+i,path,48000,2))return 5;
    }
    for(start=0;start<frames;) {
        unsigned n,count=frames-start;if(count>chunk_frames)count=chunk_frames;
        double began=seconds_now(),elapsed;
        for(n=0;n<count;++n) {
            double m[2],d[2];unsigned frame=start+n;
            if(!strcmp(argv[10],"controls")) {
                if(frame==12001&&!spm_voice_set(detail,1))return 6;
                if(frame==24013&&!spm_voice_set(detail,0))return 6;
                if(frame==39031&&!spm_voice_set(detail,.5))return 6;
            }
            if(!ms_voice_tick(&core,m)||!spm_voice_tick(detail,d,NULL))return 7;
            for(c=0;c<2;++c) {
                double mixed=m[c]+d[c];if(!isfinite(mixed)||fabs(mixed)>3.4e38)return 8;
                output[0][2*n+c]=(float)m[c];output[1][2*n+c]=(float)d[c];output[2][2*n+c]=(float)mixed;
                if(fabs(mixed)>peak)peak=fabs(mixed);
            }
        }
        elapsed=seconds_now()-began;timing[chunks++]=elapsed;total+=elapsed;if(elapsed>worst)worst=elapsed;
        if(elapsed>(double)count/48000)++overruns;
        for(i=0;i<3;++i)if(!vsl_wav_write(writers+i,output[i],count))return 9;start+=count;
    }
    for(i=0;i<3;++i)if(!vsl_wav_end(writers+i))return 10;
    qsort(timing,chunks,sizeof *timing,order);
    printf("{\"frames\":%u,\"chunk_frames\":%u,\"chunks\":%u,\"initialization_seconds\":%.17g,\"compute_seconds\":%.17g,\"worst_chunk_seconds\":%.17g,\"p99_chunk_seconds\":%.17g,\"overruns\":%u,\"peak\":%.17g,\"all_C\":true,\"room\":false}\n",
        frames,chunk_frames,chunks,init_seconds,total,worst,timing[(chunks-1)*99/100],overruns,peak);
    free(timing);spm_voice_destroy(detail);return 0;
}
