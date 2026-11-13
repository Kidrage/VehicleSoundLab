#define _CRT_SECURE_NO_WARNINGS
#include "modal_source/io.h"
#include "modal_texture/io.h"
#include "modal_texture/voice.h"
#include "spectral_texture/voice.h"
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
static MtVoice core;
static int order(const void *a,const void *b){double x=*(const double*)a,y=*(const double*)b;return(x>y)-(x<y);}
int main(int argc,char **argv) {
    SfBank *bank;SfVoice *detail;VslWavWriter writers[3];char path[2048],extra;
    const char *suffix[]={"core","detail","mix"};float output[3][480*2];
    unsigned frames,start,i,c,chunks=0,overruns=0,chunk_frames,capacity;unsigned long long seed;
    double duration,ratio,amount,init_started,init_seconds,total=0,worst=0,peak=0,*timing;
    if(argc!=11||sscanf(argv[5],"%lf %c",&duration,&extra)!=1||!isfinite(duration)||duration<1./48000||duration>120||
       sscanf(argv[6],"%llu %c",&seed,&extra)!=1||sscanf(argv[7],"%lf %c",&ratio,&extra)!=1||
       sscanf(argv[8],"%lf %c",&amount,&extra)!=1||sscanf(argv[9],"%u %c",&chunk_frames,&extra)!=1||
       !chunk_frames||chunk_frames>480||(strcmp(argv[10],"static")&&strcmp(argv[10],"controls"))) {
        fputs("source.msource amplitude.mtexture fine.sfir prefix seconds seed ratio core_amount chunk1..480 static|controls\n",stderr);return 1;
    }
    if(!ms_profile_load(argv[1],&source)||!mt_profile_load(argv[2],&amplitude)||!sf_profile_load(argv[3],&fine)||
       !mt_voice_init(&core,&source,&amplitude,(uint64_t)seed,ratio,1,amount))return 2;
    init_started=seconds_now();bank=sf_bank_create(&fine);if(!bank)return 3;
    detail=sf_voice_create(bank,(uint64_t)seed);if(!detail){sf_bank_destroy(bank);return 3;}
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
                if(frame==12001&&!mt_voice_set(&core,1.1,.8,1))return 6;
                if(frame==24013&&!mt_voice_set(&core,.9,1,0))return 6;
                if(frame==39031&&!mt_voice_set(&core,1,1,.5))return 6;
            }
            if(!mt_voice_tick(&core,m)||!sf_voice_tick(detail,d,NULL))return 7;
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
    free(timing);sf_voice_destroy(detail);sf_bank_destroy(bank);return 0;
}
