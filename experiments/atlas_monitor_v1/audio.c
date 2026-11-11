#include "audio.h"
#include <string.h>
AdControl am_default_control(void) {
    AdControl c={{VSL_PEDALS,0,0,1,1,1,1200,.8,0,0},{.25,1,0,.7,0,0,0,0}};
    return c;
}
static int process(void *context,float *pcm,unsigned frames,int stopping) {
    AmAudio *a=context;AdControl control;uint64_t generation;AdTelemetry telemetry[512];
    AdCapture capture={0};
    if(frames>512)return -1;
    EnterCriticalSection(&a->lock);control=a->control;generation=a->generation;LeaveCriticalSection(&a->lock);
    if(generation!=a->adopted) {
        if(!am_render_set(&a->render,&control))return -1;
        if(a->trace_count<AM_TRACE_CAPACITY) {
            a->trace[a->trace_count].frame=a->render.frame;a->trace[a->trace_count++].control=control;
        } else ++a->trace_overflow;
        a->adopted=generation;
    }
    if(stopping&&a->stop_frame==UINT64_MAX)a->stop_frame=a->render.frame;
    capture.telemetry=telemetry;
    if(!am_render_process(&a->render,pcm,frames,stopping,&capture))return -1;
    if(a->capture) {
        uint64_t start=a->render.frame-frames;
        if(start+frames>a->capture_frames)return -1;
        memcpy(a->capture+2*start,pcm,frames*2*sizeof(float));
    }
    EnterCriticalSection(&a->lock);a->latest=telemetry[frames-1];LeaveCriticalSection(&a->lock);
    return a->render.release==480?1:0;
}
void am_audio_init(AmAudio *a,const AdConfig *config) {
    memset(a,0,sizeof *a);InitializeCriticalSection(&a->lock);a->config=*config;
    a->control=am_default_control();wo_init(&a->device,process,a);
}
int am_audio_control(AmAudio *a,const AdControl *c) {
    if(!ad_control_valid(c,2)||(!a->config.residual_bank&&c->mix.residual_gain>0))return 0;
    EnterCriticalSection(&a->lock);a->control=*c;++a->generation;LeaveCriticalSection(&a->lock);return 1;
}
AdControl am_audio_get(AmAudio *a) {
    AdControl c;EnterCriticalSection(&a->lock);c=a->control;LeaveCriticalSection(&a->lock);return c;
}
AdTelemetry am_audio_latest(AmAudio *a) {
    AdTelemetry t;EnterCriticalSection(&a->lock);t=a->latest;LeaveCriticalSection(&a->lock);return t;
}
int am_audio_start(AmAudio *a,int muted,uint64_t limit) {
    AdControl control;
    am_audio_stop(a);control=am_audio_get(a);
    /* This device callback owns fixed stereo buffers; multichannel export is
       supported by the portable renderer through a separate offline host. */
    if(a->config.channels!=2)return 0;
    if(!am_render_init(&a->render,&a->engine,&a->config,&control))return 0;
    a->adopted=UINT64_MAX;a->stop_frame=UINT64_MAX;a->trace_count=a->trace_overflow=0;
    EnterCriticalSection(&a->lock);memset(&a->latest,0,sizeof a->latest);LeaveCriticalSection(&a->lock);
    return wo_start(&a->device,muted,limit);
}
void am_audio_stop(AmAudio *a) { wo_stop(&a->device); }
void am_audio_destroy(AmAudio *a) { wo_destroy(&a->device);DeleteCriticalSection(&a->lock); }
