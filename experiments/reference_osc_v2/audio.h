#ifndef RT_PREVIEW_AUDIO_H
#define RT_PREVIEW_AUDIO_H
#include <windows.h>
#include "pitch.h"
typedef struct {
    uint64_t frames,raw_hash;unsigned blocks,queue_empty;
    double device_seconds,wall_seconds,render_ms_max,render_ms_total,max_pitch,max_high;
    int opened;wchar_t error[256];
} RtAudioStats;
typedef struct {
    const RoModel *model;const RtTracks *tracks;RtPlayer player;double gain;
    CRITICAL_SECTION lock;HANDLE thread;volatile LONG running,stop,pitch_milli,high_percent;
    int muted;RtAudioStats stats;
} RtAudio;
void rt_audio_init(RtAudio *a,const RoModel *m,const RtTracks *t,double gain,int muted);
int rt_audio_start(RtAudio *a);
void rt_audio_stop(RtAudio *a);
void rt_audio_destroy(RtAudio *a);
void rt_audio_controls(RtAudio *a,int pitch_milli,int high_percent);
RtAudioStats rt_audio_stats(RtAudio *a);
#endif
