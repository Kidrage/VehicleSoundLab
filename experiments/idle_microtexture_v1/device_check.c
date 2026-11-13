#define _CRT_SECURE_NO_WARNINGS
#include "monitor.h"
#include "win_output/device.h"
#include "io/wav.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
typedef struct {FmRender *render;float *capture;uint64_t frame;} Capture;
static FmModels models;
static int process(void *context,float *out,unsigned frames,int stopping) {
    Capture *c=context;unsigned n;(void)stopping;
    for(n=0;n<frames;++n) {
        double main,detail,grain,level;fm_check_controls(c->frame,&main,&detail,&grain,&level);
        if(!fm_render_tick(c->render,main,detail,grain,level,out+2*n))return -1;
        memcpy(c->capture+2*c->frame,out+2*n,2*sizeof(float));++c->frame;
    }
    return 0;
}
int main(int argc,char **argv) {
    const uint64_t frames=384123;Capture c={0};FmRender *offline=NULL;WoDevice device;WoStats stats;
    VslWavWriter wav;uint64_t i,hash=UINT64_C(14695981039346656037);int ok=0,initialized=0;char path[2048];
    if(argc!=3||!fm_models_load(&models,argv[1]))return 1;
    c.capture=calloc((size_t)frames*2,sizeof(float));c.render=fm_render_create(&models,149921,.5);
    offline=fm_render_create(&models,149921,.5);if(!c.capture||!c.render||!offline)goto done;
    wo_init(&device,process,&c);initialized=1;if(!wo_start(&device,1,frames))goto done;
    while(InterlockedCompareExchange(&device.running,0,0))Sleep(20);wo_stop(&device);stats=wo_stats(&device);
    if(!stats.opened||stats.error[0]||stats.frames!=frames||c.frame!=frames)goto done;
    for(i=0;i<frames;++i) {
        double main,detail,grain,level;float output[2];unsigned b,j;
        fm_check_controls(i,&main,&detail,&grain,&level);
        if(!fm_render_tick(offline,main,detail,grain,level,output)||memcmp(output,c.capture+2*i,sizeof output))goto done;
        for(j=0;j<2;++j){uint32_t bits;memcpy(&bits,output+j,4);for(b=0;b<4;++b){hash^=(bits>>(8*b))&255u;hash*=UINT64_C(1099511628211);}}
    }
    if(hash!=stats.output_hash)goto done;
    if(snprintf(path,sizeof path,"%s_capture.wav",argv[2])<0||!vsl_wav_begin_float(&wav,path,48000,2))goto done;
    if(!vsl_wav_write(&wav,c.capture,(unsigned)frames)||!vsl_wav_end(&wav))goto done;
    printf("{\"result\":\"pass\",\"frames\":%llu,\"output_hash\":\"%016llx\",\"offline_exact\":true,\"muted\":true,\"render_ms_max\":%.17g,\"queue_empty\":%u,\"budget_exceeded\":%u,\"peak\":%.17g,\"device_seconds\":%.17g}\n",
        (unsigned long long)frames,(unsigned long long)hash,stats.render_ms_max,stats.queue_empty,stats.budget_exceeded,stats.peak,stats.device_seconds);ok=1;
done:if(initialized)wo_destroy(&device);fm_render_destroy(c.render);fm_render_destroy(offline);free(c.capture);return ok?0:2;
}
