#ifndef VSL_ATLAS_MONITOR_AUDIO_H
#define VSL_ATLAS_MONITOR_AUDIO_H
#include "atlas_monitor/render.h"
#include "core/engine.h"
#include "win_output/device.h"
#define AM_TRACE_CAPACITY 2048
typedef struct { uint64_t frame;AdControl control; } AmEvent;
typedef struct {
    CRITICAL_SECTION lock;
    AdControl control;
    AdTelemetry latest;
    uint64_t generation,adopted,stop_frame;
    AmEvent trace[AM_TRACE_CAPACITY];unsigned trace_count,trace_overflow;
    AdConfig config;
    AmRender render;VslEngine engine;
    WoDevice device;
    float *capture;size_t capture_frames;
} AmAudio;
AdControl am_default_control(void);
void am_audio_init(AmAudio *audio,const AdConfig *config);
int am_audio_control(AmAudio *audio,const AdControl *control);
AdControl am_audio_get(AmAudio *audio);
AdTelemetry am_audio_latest(AmAudio *audio);
int am_audio_start(AmAudio *audio,int muted,uint64_t frame_limit);
void am_audio_stop(AmAudio *audio);
void am_audio_destroy(AmAudio *audio);
#endif
