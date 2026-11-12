#ifndef VSL_ATLAS_MONITOR_AUDIO_H
#define VSL_ATLAS_MONITOR_AUDIO_H
#include "atlas_monitor/render.h"
#include "core/engine.h"
#include "win_output/device.h"
#include "atlas_take/player.h"
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
    AtTake take;AtPlayer player;
    uint64_t source_hash;
    int transport,ready;
    unsigned cancel_release;
    volatile LONG replay_result; /*0pending,1verified,-1failed,2cancelled. */
    float raw[1024],dna[1024],residual[1024],body[1024],events[512];
    float auxiliary[512*VSL_OBJECTS];
    float startup[1024];
    float catch_bloom[1024];
    float resonant[1024];
} AmAudio;
AdControl am_default_control(void);
void am_audio_init(AmAudio *audio,const AdConfig *config);
int am_audio_control(AmAudio *audio,const AdControl *control);
AdControl am_audio_get(AmAudio *audio);
AdTelemetry am_audio_latest(AmAudio *audio);
int am_audio_start(AmAudio *audio,int muted,uint64_t frame_limit);
int am_audio_record(AmAudio *audio,int muted,uint64_t frame_limit);
int am_audio_replay(AmAudio *audio,int muted);
int am_audio_replaying(AmAudio *audio);
void am_audio_stop(AmAudio *audio);
void am_audio_destroy(AmAudio *audio);
#endif
