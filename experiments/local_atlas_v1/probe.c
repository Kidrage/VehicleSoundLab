#define _CRT_SECURE_NO_WARNINGS
#include "assets.h"
#include "schedule.h"
#include "io/file.h"
#include "io/wav.h"
#include <errno.h>
#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#ifdef _WIN32
#include <windows.h>
#endif
static LaAssets assets;static LaSchedule schedule;static SaVoice voice;
static int integer(const char *s,uint64_t *v) {
    const char *p=s;char *end;if(!*p)return 0;
    while(*p){if(*p<'0'||*p>'9')return 0;++p;}
    errno=0;*v=strtoull(s,&end,10);return !errno&&!*end&&*v!=0;
}
static int available(const char *path) {
    FILE *f=vsl_fopen(path,"rb");if(!f)return 1;fclose(f);return 0;
}
static int run(int argc,char **argv) {
    char paths[3][4096];const char *suffix[]={".wav",".csv",".json"};
    VslWavWriter wav={0};FILE *csv=NULL,*json=NULL;uint64_t seed,chunk;
    unsigned at=0,event=0,n,j,i,old_lo=0,old_hi=0;int old_coverage=0,ok=0;
    float audio[1024];double peak=0;
    if(argc==2&&!strcmp(argv[1],"--describe")){puts("vsl.local-atlas-export/1");return 0;}
    if(argc!=6||!integer(argv[4],&seed)||!integer(argv[5],&chunk)||chunk>512)return 1;
    if(!la_assets_load(&assets,argv[1])||!la_schedule_load(&schedule,argv[2]))return 2;
    if(!sa_voice_init(&voice,&assets.bank,seed,schedule.event[0].root_hz,
                      schedule.event[0].detail,schedule.event[0].gain))return 2;
    for(i=0;i<3;++i){int k=snprintf(paths[i],sizeof paths[i],"%s%s",argv[3],suffix[i]);
        if(k<0||k>=(int)sizeof paths[i]||!available(paths[i]))return 3;}
    if(!vsl_wav_begin_float(&wav,paths[0],48000,2)||!(csv=vsl_fopen(paths[1],"wb")))goto done;
    fputs("frame,target_hz,root_hz,phase_in,phase_out,lower,upper,blend,coverage\n",csv);
    while(at<schedule.frames) {
        if(event<schedule.count&&schedule.event[event].frame==at) {
            const LaEvent *e=schedule.event+event++;
            if(!sa_voice_set(&voice,e->root_hz,e->detail,e->gain))goto done;
        }
        n=schedule.frames-at;if(n>chunk)n=(unsigned)chunk;
        if(event<schedule.count&&n>schedule.event[event].frame-at)n=schedule.event[event].frame-at;
        for(j=0;j<n;++j) {
            double x[2],phase=voice.phase;sa_voice_tick(&voice,x);
            for(i=0;i<2;++i){if(!isfinite(x[i]))goto done;audio[2*j+i]=(float)x[i];peak=fmax(peak,fabs(x[i]));}
            if((at+j)%240==0||at+j+1==schedule.frames||voice.lower!=old_lo||voice.upper!=old_hi||voice.coverage!=old_coverage)
                fprintf(csv,"%u,%.17g,%.17g,%.17g,%.17g,%u,%u,%.17g,%d\n",at+j,voice.root_target,voice.root_hz,phase,voice.phase,voice.lower,voice.upper,voice.blend,voice.coverage);
            old_lo=voice.lower;old_hi=voice.upper;old_coverage=voice.coverage;
        }
        if(!vsl_wav_write(&wav,audio,n))goto done;at+=n;
    }
    if(ferror(csv)||!vsl_wav_end(&wav))goto done;
    json=vsl_fopen(paths[2],"wb");if(!json)goto done;
    fprintf(json,"{\"protocol\":\"vsl.local-atlas-export/1\",\"frames\":%u,\"anchors\":%u,\"harmonics\":%u,\"seed\":%llu,\"block\":%llu,\"peak\":%.17g,\"root_hz\":[",
        schedule.frames,assets.bank.count,assets.bank.harmonics,(unsigned long long)seed,(unsigned long long)chunk,peak);
    for(i=0;i<assets.bank.count;++i)fprintf(json,"%s%.17g",i?",":"",assets.models[i].base_hz);
    fputs("],\"offsets\":[",json);
    for(i=0;i<assets.bank.count;++i)fprintf(json,"%s%.17g",i?",":"",assets.bank.offset[i]);
    fputs("],\"texture_updates\":[",json);
    for(i=0;i<assets.bank.count;++i)fprintf(json,"%s%llu",i?",":"",(unsigned long long)voice.texture[i].updates);
    fprintf(json,"],\"source_frame\":%llu,\"new_room\":false,\"PCM_loop\":false}\n",(unsigned long long)voice.frame);
    if(ferror(json))goto done;ok=1;
done:if(wav.file&&!vsl_wav_end(&wav))ok=0;
    if(csv&&fclose(csv))ok=0;if(json&&fclose(json))ok=0;return ok?0:4;
}
#ifdef _WIN32
int wmain(int argc,wchar_t **wide) {
    char **args=calloc((size_t)argc,sizeof *args);int i,result=2;if(!args)return 2;
    for(i=0;i<argc;++i){int n=WideCharToMultiByte(CP_UTF8,0,wide[i],-1,NULL,0,NULL,NULL);
        if(!n||!(args[i]=malloc((size_t)n))||!WideCharToMultiByte(CP_UTF8,0,wide[i],-1,args[i],n,NULL,NULL))goto done;}
    result=run(argc,args);
done:for(i=0;i<argc;++i)free(args[i]);free(args);return result;
}
#else
int main(int argc,char **argv){return run(argc,argv);}
#endif
