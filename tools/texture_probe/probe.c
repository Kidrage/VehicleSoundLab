#define _CRT_SECURE_NO_WARNINGS
/* Offline measurement host of the frozen V015 library. No new DSP model. */
#include "io/take_file.h"
#include "io/take_render.h"
#include "io/render_session.h"
#include <stdlib.h>
#include <stdio.h>
#include <math.h>
#include <inttypes.h>
#include <string.h>
#ifdef _WIN32
#include <windows.h>
#endif
static int run(int argc,char **argv) {
    VslTake take={0};VslEngine *e=NULL;VslParams p=vsl_default_params(VSL_V10);
    char name[4096],stems[4096],trace[4096];float audio[1024];unsigned n;uint64_t hash=0;int ok=0,compat;
    if(argc!=6) { fputs("texture_probe prefix rpm signed_load pure_osc compat_pcm\n",stderr);return 1; }
    p.rpm=atof(argv[2]);p.load=atof(argv[3]);p.pure_osc=atoi(argv[4]);compat=atoi(argv[5]);
    if(!isfinite(p.rpm)||p.rpm<0||p.rpm>10000||!isfinite(p.load)||p.load<-1||p.load>1||p.pure_osc<0||p.pure_osc>1||strlen(argv[1])>3900)return 1;
    e=malloc(sizeof *e);if(!e||!vsl_take_allocate(&take,4))goto done;
    vsl_init(e,48000,48271);vsl_set_params(e,&p);if(!vsl_take_begin(&take,e))goto done;
    while(e->frame<288000) {
        n=(unsigned)(288000-e->frame);if(n>512)n=512;
        if(!vsl_take_record(&take,e->frame,&e->target))goto done;
        vsl_process(e,audio,n);vsl_take_commit(&take,audio,n);
    }
    vsl_take_finish(&take);snprintf(name,sizeof name,"%s.vsltake",argv[1]);
    if(!vsl_take_save(name,&take))goto done;
    snprintf(name,sizeof name,"%s.wav",argv[1]);snprintf(stems,sizeof stems,"%s_source",argv[1]);
    snprintf(trace,sizeof trace,"%s.csv",argv[1]);
    if(!vsl_take_render(&take,name,2,trace,stems,&hash)||hash!=take.audio_hash)goto done;
    if(compat) {
        snprintf(name,sizeof name,"%s_compat.wav",argv[1]);
        if(!vsl_render_file(name,&p,6,0,NULL,NULL))goto done;
    }
    printf("DSP %s | frames %" PRIu64 " | stereo hash %016" PRIx64 " | float and source export verified\n",VSL_VERSION,take.frames,take.audio_hash);ok=1;
done:
    vsl_take_free(&take);free(e);return ok?0:2;
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
