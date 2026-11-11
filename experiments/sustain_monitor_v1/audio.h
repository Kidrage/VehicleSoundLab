#ifndef VSL_SUSTAIN_MONITOR_AUDIO_H
#define VSL_SUSTAIN_MONITOR_AUDIO_H
#include <windows.h>
#include "render.h"
typedef struct {
    uint64_t frames,raw_hash;unsigned blocks,queue_empty;
    double device_seconds,wall_seconds,startup_seconds,playback_wall_seconds;
    double render_ms_total,render_ms_max,min_pitch,max_pitch,min_detail,max_detail,min_attenuation,peak;
    int opened;wchar_t error[256];
} SmStats;
typedef struct {
    const SuModel *model;SmRender render;CRITICAL_SECTION lock;HANDLE thread;
    volatile LONG running,stop,pitch,detail,db;int muted;
    uint64_t frame_limit;float *capture;size_t capture_frames;
    SmStats stats;
} SmAudio;
void sm_audio_init(SmAudio *audio,const SuModel *model,int muted);
void sm_audio_controls(SmAudio *audio,int pitch,int detail,int db);
int sm_audio_start(SmAudio *audio);
void sm_audio_stop(SmAudio *audio);
void sm_audio_destroy(SmAudio *audio);
SmStats sm_audio_stats(SmAudio *audio);
#endif
