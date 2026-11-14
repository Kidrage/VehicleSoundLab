#define _CRT_SECURE_NO_WARNINGS
#include "dna_atlas/voice.h"
#include "io/wav.h"
#include <errno.h>
#include <math.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#ifdef _WIN32
#include <windows.h>
#endif
/* Offline explicit-root adapter; same SaVoice as driving, unity stereo, no
   fades/room/PCM replay. High-root profiles never enter legacy SdVoice. */
static SdProfile profile;
static SaBank bank;
static SaVoice voice;
static int number(const char *s,double lo,double hi,double *v) {
    char *end;errno=0;*v=strtod(s,&end);
    return end!=s&&!*end&&!errno&&isfinite(*v)&&*v>=lo&&*v<=hi;
}
static int integer(const char *s,uint64_t *v) {
    const char *p=s;char *end;if(!*p)return 0;
    while(*p){if(*p<'0'||*p>'9')return 0;++p;}
    errno=0;*v=strtoull(s,&end,10);return !errno&&!*end&&*v!=0;
}
static int run(int argc,char **argv) {
    VslWavWriter w={0};const SdProfile *models[1]={&profile};
    double seconds,root,detail,block[1024];float out[1024];
    uint64_t seed,chunk;unsigned frames,at=0,n,i;int ok=0;
    if(argc==2&&!strcmp(argv[1],"--describe")){puts("vsl.sound-dna-bandlimited-export/1");return 0;}
    if(argc!=8){fprintf(stderr,"Usage: sound_dna_bandlimited_export model out.wav seconds root_hz detail seed block_frames\n");return 1;}
    if(!number(argv[3],1./48000,60,&seconds)||!number(argv[4],0,1000,&root)||
       !number(argv[5],0,1,&detail)||!integer(argv[6],&seed)||!integer(argv[7],&chunk)||chunk>512)return 1;
    if(!sd_profile_load_bandlimited(argv[1],&profile)||!sa_bank_init_bandlimited(&bank,models,1,0)||
       !sa_voice_init(&voice,&bank,seed,root,detail,1))return 2;
    frames=(unsigned)(seconds*48000+.5);
    if(!vsl_wav_begin_float(&w,argv[2],48000,2))goto done;
    while(at<frames) {
        n=frames-at;if(n>chunk)n=(unsigned)chunk;sa_voice_process(&voice,block,n);
        for(i=0;i<2*n;++i){if(!isfinite(block[i]))goto done;out[i]=(float)block[i];}
        if(!vsl_wav_write(&w,out,n))goto done;at+=n;
    }
    ok=1;
done:if(w.file)ok=vsl_wav_end(&w)&&ok;return ok?0:3;
}
#ifdef _WIN32
int wmain(int argc,wchar_t **wide) {
    int i,result=2;char **args=calloc((size_t)argc,sizeof *args);if(!args)return 2;
    for(i=0;i<argc;++i){int n=WideCharToMultiByte(CP_UTF8,0,wide[i],-1,NULL,0,NULL,NULL);
        if(!n||!(args[i]=malloc((size_t)n))||!WideCharToMultiByte(CP_UTF8,0,wide[i],-1,args[i],n,NULL,NULL))goto done;}
    result=run(argc,args);
done:for(i=0;i<argc;++i)free(args[i]);free(args);return result;
}
#else
int main(int argc,char **argv){return run(argc,argv);}
#endif
