#define _CRT_SECURE_NO_WARNINGS
#include "residual_dense/voice.h"
#include "sound_residual/voice.h"
#include "io/file.h"
#include "io/wav.h"
#include <errno.h>
#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <windows.h>
static RdVoice dense;
static SrVoice old;
static double elapsed[12001];
static int compare(const void *a,const void *b) {double x=*(const double*)a,y=*(const double*)b;return (x>y)-(x<y);}
static int number(const char *s,double *v) {char *end;*v=strtod(s,&end);return end!=s&&!*end&&isfinite(*v);}
static int run(int argc,char **argv) {
    SrProfile p;VslWavWriter w={0};FILE *stream;char *end;double seconds,pitch,gain,peak_value,block_value;
    double raw[1024],total_ms=0,max_ms=0,checksum=0;float pcm[1024];
    unsigned counts[SR_MAX_BANDS]={0},peak,block,frames,at=0,n,i,timed=0,overruns=0,carrier_count;
    uint64_t seed;LARGE_INTEGER frequency,before,after;int ok=0,write_file;
    if(argc!=9||!number(argv[3],&seconds)||seconds<=1||seconds>60||!number(argv[4],&pitch)||pitch<.9||pitch>1.1||
       !number(argv[5],&gain)||gain<0||gain>1||!number(argv[7],&peak_value)||
       !(peak_value==0||peak_value==32||peak_value==64||peak_value==128||peak_value==256)||
       !number(argv[8],&block_value)||!(block_value==240||block_value==512))return 1;
    peak=(unsigned)peak_value;block=(unsigned)block_value;
    errno=0;seed=strtoull(argv[6],&end,10);if(end==argv[6]||*end||argv[6][0]=='-'||errno==ERANGE)return 1;
    stream=vsl_fopen(argv[1],"rb");if(!stream)return 2;
    ok=sr_profile_read(stream,&p);if(fclose(stream))ok=0;if(!ok)return 2;
    for(i=0;i<p.bands;++i) {
        double desired=ceil((p.band[i].high-p.band[i].low)*peak/2000.);
        counts[i]=peak?(unsigned)fmin(256,fmax(32,desired)):p.partials;
    }
    if(peak) {if(!rd_voice_init(&dense,&p,counts,seed,pitch,gain))return 2;carrier_count=dense.cloud.count;}
    else {if(!sr_voice_init(&old,&p,seed,pitch,gain))return 2;carrier_count=old.cloud.count;}
    write_file=strcmp(argv[2],"-")!=0;
    if(write_file&&!vsl_wav_begin_float(&w,argv[2],48000,2))return 2;
    if(!QueryPerformanceFrequency(&frequency)){ok=0;goto done;}
    frames=(unsigned)(seconds*48000+.5);ok=1;
    while(at<frames) {
        double ms;n=frames-at;if(n>block)n=block;
        QueryPerformanceCounter(&before);
        if(peak)ok=rd_voice_process(&dense,raw,n);else ok=sr_voice_process(&old,raw,n);
        QueryPerformanceCounter(&after);if(!ok)break;
        ms=(after.QuadPart-before.QuadPart)*1000./frequency.QuadPart;
        if(at>=48000) {if(timed>=12001){ok=0;break;}elapsed[timed++]=ms;total_ms+=ms;if(ms>max_ms)max_ms=ms;if(ms>block/48.)++overruns;}
        checksum+=raw[0]+raw[2*n-1];
        if(write_file) {for(i=0;i<2*n;++i)pcm[i]=(float)raw[i];if(!vsl_wav_write(&w,pcm,n)){ok=0;break;}}
        at+=n;
    }
    if(ok&&timed) {
        qsort(elapsed,timed,sizeof elapsed[0],compare);
        printf("{\"mode\":\"%s\",\"peak\":%u,\"block\":%u,\"carriers\":%u,\"voice_bytes\":%zu,\"counts\":[",peak?"dense":"legacy",peak,block,carrier_count,peak?sizeof dense:sizeof old);
        for(i=0;i<p.bands;++i)printf("%s%u",i?",":"",counts[i]);
        printf("],\"timed_blocks\":%u,\"process_ms\":%.17g,\"median_ms\":%.17g,\"p95_ms\":%.17g,\"maximum_ms\":%.17g,\"overruns\":%u,\"checksum\":%.17g}\n",timed,total_ms,elapsed[timed/2],elapsed[(unsigned)(.95*(timed-1))],max_ms,overruns,checksum);
    }
done:if(w.file)ok=vsl_wav_end(&w)&&ok;return ok?0:3;
}
int wmain(int argc,wchar_t **wide) {
    char **args=calloc((size_t)argc,sizeof *args);int i,result=2;if(!args)return 2;
    for(i=0;i<argc;++i) {
        int n=WideCharToMultiByte(CP_UTF8,0,wide[i],-1,NULL,0,NULL,NULL);
        if(!n||!(args[i]=malloc((size_t)n))||!WideCharToMultiByte(CP_UTF8,0,wide[i],-1,args[i],n,NULL,NULL))goto done;
    }
    result=run(argc,args);
done:for(i=0;i<argc;++i)free(args[i]);free(args);return result;
}
