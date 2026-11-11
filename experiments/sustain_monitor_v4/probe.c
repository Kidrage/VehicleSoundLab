#define _CRT_SECURE_NO_WARNINGS
#include "render.h"
#include "io/wav.h"
#include <stdio.h>
#include <stdlib.h>
#include <math.h>
#include <windows.h>
static SdProfile dna;static LrProfile low;static SmRender render;
/* DNA LOW OUTPUT SECONDS PITCH AMOUNT MODE stem:0mix/1DNAraw/2lowraw */
static int run(int argc,char **argv){VslWavWriter w={0};double seconds,pitch,amount;char *end;unsigned frames,at=0,n,i;float raw[1024],out[1024],body[512],stereo[1024];int ok=0,mode,stem;
    if(argc!=9)return 1;
    seconds=strtod(argv[4],&end);if(end==argv[4]||*end||!isfinite(seconds)||seconds<=0||seconds>60)return 1;
    pitch=strtod(argv[5],&end);if(end==argv[5]||*end||!isfinite(pitch)||pitch<.9||pitch>1.1)return 1;
    amount=strtod(argv[6],&end);if(end==argv[6]||*end||!isfinite(amount)||amount<0||amount>1)return 1;
    mode=(int)strtol(argv[7],&end,10);if(end==argv[7]||*end||mode<0||mode>2)return 1;
    stem=(int)strtol(argv[8],&end,10);if(end==argv[8]||*end||stem<0||stem>2)return 1;
    if(!sd_profile_load(argv[1],&dna)||!lr_profile_load(argv[2],&low)||!sm_render_init(&render,&dna,&low,(int)(pitch*1000+.5),1000,0,(int)(amount*1000+.5),mode))return 2;
    if(!vsl_wav_begin_float(&w,argv[3],48000,2))return 2;frames=(unsigned)(seconds*48000+.5);
    while(at<frames){n=frames-at;if(n>512)n=512;sm_render_process(&render,raw,body,out,n,0);
        for(i=0;i<n;++i)stereo[2*i]=stereo[2*i+1]=body[i];
        if(!vsl_wav_write(&w,stem==1?raw:stem==2?stereo:out,n))goto done;at+=n;}
    ok=1;
done:if(w.file)ok=vsl_wav_end(&w)&&ok;return ok?0:3;
}
int wmain(int argc,wchar_t **wide){int i,result=2;char **args=calloc((size_t)argc,sizeof *args);if(!args)return 2;
    for(i=0;i<argc;++i){int n=WideCharToMultiByte(CP_UTF8,0,wide[i],-1,NULL,0,NULL,NULL);
        if(!n||!(args[i]=malloc((size_t)n))||!WideCharToMultiByte(CP_UTF8,0,wide[i],-1,args[i],n,NULL,NULL))goto done;}
    result=run(argc,args);
done:for(i=0;i<argc;++i)free(args[i]);free(args);return result;}
