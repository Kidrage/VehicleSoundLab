#define _CRT_SECURE_NO_WARNINGS
#include "io/take_file.h"
#include "io/take_render.h"
#include <stdlib.h>
#include <stdio.h>
#include <string.h>
#include <inttypes.h>
#ifdef _WIN32
#include <windows.h>
#endif
static int run(int argc,char **argv) {
    VslTake take={0};const char *trace=NULL,*stems=NULL;int channels=2,i,ok;uint64_t hash=0;
    if(argc<3) { puts("vsl_take_render input.vsltake output.wav [--channels 2|12] [--trace file.csv] [--stems prefix]");return 1; }
    for(i=3;i<argc;++i) {
        if(!strcmp(argv[i],"--channels")&&i+1<argc)channels=atoi(argv[++i]);
        else if(!strcmp(argv[i],"--trace")&&i+1<argc)trace=argv[++i];
        else if(!strcmp(argv[i],"--stems")&&i+1<argc)stems=argv[++i];
        else return 1;
    }
    if(!vsl_take_load(argv[1],&take)) { fputs("Invalid take or incompatible DSP version\n",stderr);return 2; }
    ok=vsl_take_render(&take,argv[2],channels,trace,stems,&hash);
    if(ok)printf("%" PRIu64 " frames | %u events | %d channels | DSP %s | stereo hash %s\n",take.frames,take.count,channels,VSL_VERSION,channels==2?"verified":"not applicable");
    else fputs("Render or stereo reconstruction hash failed\n",stderr);
    vsl_take_free(&take);return ok?0:2;
}
#ifdef _WIN32
int wmain(int argc,wchar_t **wide) {
    char **args=calloc((size_t)argc,sizeof *args);int i,result=2;if(!args)return 2;
    for(i=0;i<argc;++i) {
        int n=WideCharToMultiByte(CP_UTF8,0,wide[i],-1,NULL,0,NULL,NULL);args[i]=malloc(n);
        if(!args[i])goto done;WideCharToMultiByte(CP_UTF8,0,wide[i],-1,args[i],n,NULL,NULL);
    }
    result=run(argc,args);
done:
    for(i=0;i<argc;++i)free(args[i]);free(args);return result;
}
#else
int main(int argc,char **argv) { return run(argc,argv); }
#endif
