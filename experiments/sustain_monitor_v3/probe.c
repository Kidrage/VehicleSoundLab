#define _CRT_SECURE_NO_WARNINGS
#include "render.h"
#include "io/wav.h"
#include <stdio.h>
#include <stdlib.h>
#include <math.h>
#ifdef _WIN32
#include <windows.h>
#endif
static SdProfile profile;static SmRender render;
static int run(int argc,char **argv){
    VslWavWriter w={0};double seconds,pitch,amount;char *end;unsigned frames,at=0,n;float raw[1024],out[1024];int ok=0;
    if(argc!=7)return 1;
    seconds=strtod(argv[3],&end);if(end==argv[3]||*end||!isfinite(seconds)||seconds<=0||seconds>60)return 1;
    pitch=strtod(argv[4],&end);if(end==argv[4]||*end||!isfinite(pitch)||pitch<.9||pitch>1.1)return 1;
    amount=strtod(argv[5],&end);if(end==argv[5]||*end||!isfinite(amount)||amount<0||amount>1)return 1;
    if(!sd_profile_load(argv[1],&profile)||!sm_render_init(&render,&profile,(int)(pitch*1000+.5),(int)(amount*1000+.5),0))return 2;
    if(!vsl_wav_begin_float(&w,argv[2],48000,2))return 2;frames=(unsigned)(seconds*48000+.5);
    while(at<frames){n=frames-at;if(n>512)n=512;sm_render_process(&render,raw,out,n,0);
        if(!vsl_wav_write(&w,argv[6][0]=='1'?raw:out,n))goto done;at+=n;}
    ok=1;
done:if(w.file)ok=vsl_wav_end(&w)&&ok;return ok?0:3;
}
#ifdef _WIN32
int wmain(int argc,wchar_t **wide){int i,result=2;char **args=calloc((size_t)argc,sizeof *args);if(!args)return 2;
    for(i=0;i<argc;++i){int n=WideCharToMultiByte(CP_UTF8,0,wide[i],-1,NULL,0,NULL,NULL);
        if(!n||!(args[i]=malloc((size_t)n))||!WideCharToMultiByte(CP_UTF8,0,wide[i],-1,args[i],n,NULL,NULL))goto done;}
    result=run(argc,args);
done:for(i=0;i<argc;++i)free(args[i]);free(args);return result;}
#else
int main(int argc,char **argv){return run(argc,argv);}
#endif
