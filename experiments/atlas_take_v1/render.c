#define _CRT_SECURE_NO_WARNINGS
#include "atlas_take/player.h"
#include "atlas_take_io/file.h"
#include "io/wav.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#ifdef _WIN32
#include <windows.h>
#endif
static int run(int argc,char **argv) {
    AtTake take={0};AtPlayer *p=NULL;VslEngine *e=NULL;VslWavWriter wav={0};float output[512*12];int channels=2,ok=0;
    if(argc!=3&&argc!=5){fputs("VslAtlasTake_render input.vslrun output.wav [--channels 2|12]\n",stderr);return 2;}
    if(argc==5){if(strcmp(argv[3],"--channels")||(strcmp(argv[4],"2")&&strcmp(argv[4],"12")))return 2;channels=atoi(argv[4]);}
    p=calloc(1,sizeof *p);e=calloc(1,sizeof *e);
    if(!p||!e||!at_take_load(&take,argv[1])||!at_player_init(p,e,&take,channels)||!vsl_wav_begin_float(&wav,argv[2],48000,channels))goto done;
    while(!at_player_complete(p)) {
        unsigned n=at_player_process(p,output,512,NULL);if(!n||!vsl_wav_write(&wav,output,n))goto done;
    }
    ok=at_player_verified(p);
    printf("{\"frames\":%llu,\"channels\":%d,\"verified\":%s,\"audio_hash\":\"%016llx\",\"source_hash\":\"%016llx\",\"render_id\":\"%s\"}\n",
        (unsigned long long)take.frames,channels,ok?"true":"false",(unsigned long long)p->audio_hash,(unsigned long long)p->source_hash,at_render_id());
done:if(wav.file&&!vsl_wav_end(&wav))ok=0;at_take_free(&take);free(p);free(e);
    if(!ok)fputs("Render failed: inspect take version, integrity or output path\n",stderr);return ok?0:3;
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
