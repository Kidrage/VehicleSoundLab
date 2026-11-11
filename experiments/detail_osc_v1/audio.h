#ifndef VSL_DETAIL_AUDIO_H
#define VSL_DETAIL_AUDIO_H
#include <windows.h>
#include "stream.h"
typedef struct {
    uint64_t frames,raw_hash,loops;unsigned blocks,queue_empty;
    double device_seconds,wall_seconds,startup_seconds,playback_wall_seconds,render_ms_max,render_ms_total,max_pitch,min_gain,position;
    int opened;wchar_t error[256];
} DeStats;
typedef struct {
    const DoModel *model;DePlayer player;CRITICAL_SECTION lock;HANDLE thread;
    volatile LONG running,stop,pitch_milli,level_db,loop;int muted;DeStats stats;
} DeAudio;
void de_audio_init(DeAudio *audio,const DoModel *model,int muted);
void de_audio_controls(DeAudio *audio,int pitch_milli,int level_db,int loop);
int de_audio_start(DeAudio *audio);
void de_audio_stop(DeAudio *audio);
void de_audio_destroy(DeAudio *audio);
DeStats de_audio_stats(DeAudio *audio);
#endif
