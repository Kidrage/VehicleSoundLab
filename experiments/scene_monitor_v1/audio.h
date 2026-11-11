#ifndef VSL_SCENE_MONITOR_AUDIO_H
#define VSL_SCENE_MONITOR_AUDIO_H
#include <windows.h>
#include "scene_monitor/render.h"
#define SA_TRACE_CAPACITY 256

typedef struct { uint64_t frame; SmoControl control; } SaEvent;
typedef struct {
    uint64_t frames, dna_hash, low_hash, output_hash;
    unsigned blocks, queue_empty, changes, trace_overflow;
    double device_seconds, wall_seconds, render_ms_total, render_ms_max, peak;
    int opened; wchar_t error[256];
} SaStats;
typedef struct {
    DsSceneConfig config;
    SmoControl control;
    uint64_t generation;
    SmoRender render;
    VslEngine spatial;
    CRITICAL_SECTION lock;
    HANDLE thread;
    volatile LONG running, stop;
    int muted;
    uint64_t frame_limit, stop_frame;
    float *capture; size_t capture_frames;
    SaEvent trace[SA_TRACE_CAPACITY]; unsigned trace_count;
    SaStats stats;
} SaAudio;

void sa_audio_init(SaAudio *audio, const DsSceneConfig *config, const SmoControl *control, int muted);
int sa_audio_controls(SaAudio *audio, const SmoControl *control);
SmoControl sa_audio_control(SaAudio *audio);
int sa_audio_start(SaAudio *audio);
void sa_audio_stop(SaAudio *audio);
void sa_audio_destroy(SaAudio *audio);
SaStats sa_audio_stats(SaAudio *audio);
#endif
