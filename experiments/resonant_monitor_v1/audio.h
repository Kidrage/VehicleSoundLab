#ifndef VSL_RESONANT_MONITOR_AUDIO_H
#define VSL_RESONANT_MONITOR_AUDIO_H
#include "models.h"
#include "win_output/device.h"
#define RSM_TRACE_CAPACITY 512
typedef struct {uint64_t frame;RsmControl control;} RsmEvent;
typedef struct {
    RssConfig config;RsmControl control;RsmRender render;
    WoDevice device;CRITICAL_SECTION lock;uint64_t generation,adopted;
    RsmEvent trace[RSM_TRACE_CAPACITY],pending;
    unsigned trace_count,trace_overflow;int pending_change;
    uint64_t stop_frame,pending_stop;
    float *capture;size_t capture_frames;
} RsmAudio;
void rsm_audio_init(RsmAudio *audio,const RssConfig *config,const RsmControl *control);
int rsm_audio_control(RsmAudio *audio,const RsmControl *control);
RsmControl rsm_audio_get(RsmAudio *audio);
/* Non-RT, stop before rebind; model storage remains owned by the host. */
void rsm_audio_rebind(RsmAudio *audio,const RssConfig *config,const RsmControl *control);
int rsm_audio_start(RsmAudio *audio,int muted,uint64_t frames);
void rsm_audio_stop(RsmAudio *audio);
void rsm_audio_destroy(RsmAudio *audio);
#endif
