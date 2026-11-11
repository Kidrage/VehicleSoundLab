#ifndef VSL_AUDIO_DEVICE_H
#define VSL_AUDIO_DEVICE_H
#include <windows.h>
#include "core/engine.h"
#include "session/take.h"
#define VSL_DEVICE_BLOCK 512
typedef struct {
    CRITICAL_SECTION lock;
    HANDLE thread;
    volatile LONG stop, running;
    volatile LONG replay_fade;
    int take_mode; /* configured while stopped: 0 monitor, 1 record, 2 replay */
    VslTake *take;
    VslTakePlayer player;
    uint64_t take_frames;
    unsigned take_events;
    int take_limit,take_hash_match;
    VslParams actual_target;
    VslEngine *engine;
    VslParams params;
    int drive, diagnostic_mute;
    double seconds,peak,rpm,load;
    VslDrive state;
    VslVoicing voice;
    double propagation_mix;
    unsigned propagation_clamped_paths;
    double character_pressure_mix,character_structure_mix;
    unsigned character_events;
    double response_shape_mix;
    uint64_t response_pressure_events;
    double event_color_mix,event_color_max_mod;
    uint64_t event_color_events;
    double pulse_mix;uint64_t pulse_events;unsigned pulse_overflow;
    double render_ms_max,render_ms_total;
    unsigned rendered_blocks;
    double worker_wall_seconds,device_seconds;
    unsigned queue_empty_observations;
    float scope[256];
    wchar_t error[256];
} VslAudio;
void vsl_audio_init(VslAudio *a);
int vsl_audio_start(VslAudio *a);
void vsl_audio_stop(VslAudio *a);
void vsl_audio_destroy(VslAudio *a);
void vsl_audio_params(VslAudio *a,const VslParams *p,int drive);
#endif
