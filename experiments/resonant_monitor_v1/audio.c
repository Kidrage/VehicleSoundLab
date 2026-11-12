#include "audio.h"
#include <string.h>
static int process(void *context,float *pcm,unsigned frames,int stopping) {
    RsmAudio *a=context;RsmControl p;uint64_t generation,start=a->render.frame;
    if(frames>512)return -1;
    EnterCriticalSection(&a->lock);p=a->control;generation=a->generation;LeaveCriticalSection(&a->lock);
    a->pending_change=0;a->pending_stop=UINT64_MAX;
    if(generation!=a->adopted) {
        if(!rsm_render_set(&a->render,&p))return -1;
        a->pending.frame=start;a->pending.control=p;a->pending_change=1;a->adopted=generation;
    }
    if(stopping&&a->stop_frame==UINT64_MAX)a->pending_stop=start;
    if(!rsm_render_process(&a->render,pcm,frames,stopping,NULL))return -1;
    if(a->capture) {
        if(start+frames>a->capture_frames)return -1;
        memcpy(a->capture+2*start,pcm,frames*2*sizeof(float));
    }
    return a->render.release==480?1:0;
}
static void submitted(void *context,unsigned frames,uint64_t hash) {
    RsmAudio *a=context;(void)frames;(void)hash;
    if(a->pending_change) {
        if(a->trace_count<RSM_TRACE_CAPACITY)a->trace[a->trace_count++]=a->pending;
        else ++a->trace_overflow;
    }
    if(a->pending_stop!=UINT64_MAX)a->stop_frame=a->pending_stop;
}
void rsm_audio_init(RsmAudio *a,const RssConfig *c,const RsmControl *p) {
    memset(a,0,sizeof *a);a->config=*c;a->control=*p;InitializeCriticalSection(&a->lock);
    wo_init(&a->device,process,a);a->device.submitted=submitted;
}
int rsm_audio_control(RsmAudio *a,const RsmControl *p) {
    if(!a||!rsm_control_valid(p)||(!a->config.source.low&&p->source.source.low_gain>0)||
       (!a->config.detail&&p->source.detail_gain>0))return 0;
    EnterCriticalSection(&a->lock);a->control=*p;++a->generation;LeaveCriticalSection(&a->lock);return 1;
}
RsmControl rsm_audio_get(RsmAudio *a) {
    RsmControl p;EnterCriticalSection(&a->lock);p=a->control;LeaveCriticalSection(&a->lock);return p;
}
void rsm_audio_rebind(RsmAudio *a,const RssConfig *c,const RsmControl *p) {
    rsm_audio_stop(a);a->config=*c;
    EnterCriticalSection(&a->lock);a->control=*p;++a->generation;LeaveCriticalSection(&a->lock);
}
int rsm_audio_start(RsmAudio *a,int muted,uint64_t frames) {
    RsmControl p;
    rsm_audio_stop(a);p=rsm_audio_get(a);
    if(!rsm_render_init(&a->render,&a->config,2,&p))return 0;
    a->adopted=UINT64_MAX;a->stop_frame=a->pending_stop=UINT64_MAX;
    a->trace_count=a->trace_overflow=0;a->pending_change=0;
    return wo_start(&a->device,muted,frames);
}
void rsm_audio_stop(RsmAudio *a) {wo_stop(&a->device);}
void rsm_audio_destroy(RsmAudio *a) {wo_destroy(&a->device);DeleteCriticalSection(&a->lock);}
