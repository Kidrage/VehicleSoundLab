#define _CRT_SECURE_NO_WARNINGS
#include "residual_motion/voice.h"
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
static RmVoice voice;
static int number(const char *text,double low,double high,double *v) {
    char *end;errno=0;*v=strtod(text,&end);return end!=text&&!*end&&errno!=ERANGE&&isfinite(*v)&&*v>=low&&*v<=high;
}
static int seed_value(const char *text,uint64_t *seed) {
    char *end;errno=0;*seed=strtoull(text,&end,10);return end!=text&&!*end&&errno!=ERANGE&&*text!='-';
}
static int run(int argc,char **argv) {
    SrProfile source;RmProfile motion;VslWavWriter output={0},raw_output={0};FILE *stream=NULL,*trace=NULL;
    double seconds,pitch,gain,amount=0,samples[960],raw[960],peak=0,energy=0;float pcm[960],base[960];
    unsigned frames,at=0,n,i;uint64_t source_seed,motion_seed;int ok=0,transition;
    if(argc!=10&&argc!=12){fprintf(stderr,"source.residual motion output.wav seconds pitch gain amount|rise-fall source_seed motion_seed [raw.wav trace.csv]\n");return 1;}
    transition=!strcmp(argv[7],"rise-fall");
    if(!number(argv[4],.1,120,&seconds)||!number(argv[5],.9,1.1,&pitch)||!number(argv[6],0,1,&gain)||
       (!transition&&!number(argv[7],0,1,&amount))||!seed_value(argv[8],&source_seed)||!seed_value(argv[9],&motion_seed))return 1;
    stream=vsl_fopen(argv[1],"rb");if(!stream)return 2;
    ok=sr_profile_read(stream,&source);if(fclose(stream))ok=0;if(!ok)return 2;
    stream=vsl_fopen(argv[2],"rb");if(!stream)return 2;
    ok=rm_profile_read(stream,&motion);if(fclose(stream))ok=0;if(!ok)return 2;
    if(!rm_voice_init(&voice,&source,&motion,source_seed,motion_seed,pitch,gain,amount)||
       !vsl_wav_begin_float(&output,argv[3],48000,2))return 2;
    if(argc==12) {
        trace=vsl_fopen(argv[11],"wb");
        if(!trace||!vsl_wav_begin_float(&raw_output,argv[10],48000,2))ok=0;
        if(trace){fprintf(trace,"frame,amount");for(i=0;i<motion.bands;++i)fprintf(trace,",band%u",i);fputc('\n',trace);}
    }
    frames=(unsigned)(seconds*48000+.5);
    while(ok&&at<frames) {
        n=frames-at;if(n>480)n=480;
        if(transition)rm_voice_set(&voice,pitch,gain,at>=96000&&at<288000?1:0);
        if(trace) {
            RmEnvelope copy=voice.motion;double g[SR_MAX_BANDS];rm_envelope_tick(&copy,g);
            fprintf(trace,"%u,%.17g",at,copy.amount);
            for(i=0;i<motion.bands;++i)fprintf(trace,",%.17g",g[i]);fputc('\n',trace);
        }
        if(!rm_voice_process(&voice,samples,raw,n)){ok=0;break;}
        for(i=0;i<2*n;++i){pcm[i]=(float)samples[i];base[i]=(float)raw[i];peak=fmax(peak,fabs(samples[i]));energy+=samples[i]*samples[i];}
        if(!vsl_wav_write(&output,pcm,n)||(argc==12&&!vsl_wav_write(&raw_output,base,n))){ok=0;break;}at+=n;
    }
    if(!vsl_wav_end(&output))ok=0;
    if(argc==12&&!vsl_wav_end(&raw_output))ok=0;
    if(trace&&fclose(trace))ok=0;
    if(ok)printf("{\"frames\":%u,\"peak\":%.17g,\"rms\":%.17g}\n",at,peak,sqrt(energy/(2*at)));
    return ok?0:3;
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
