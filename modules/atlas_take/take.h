#ifndef VSL_ATLAS_TAKE_H
#define VSL_ATLAS_TAKE_H
#include "assets.h"
#define AT_MAX_EVENTS 65536u
#define AT_MAX_FRAMES (UINT64_C(48000)*600)
#define AT_HASH_INITIAL UINT64_C(14695981039346656037)
typedef struct {uint64_t frame;AdControl control;} AtEvent;
typedef struct {
    AtAssets *assets;
    AtEvent *events;
    unsigned count,capacity;
    AdControl initial;
    uint64_t frames,stop_frame,audio_hash,source_hash;
    int overflow;
} AtTake;
/* Zero initialize before first allocation; free before allocating again.
   Allocate/copy/validate outside audio; event/commit are bounded RT calls.
   Control events are staged before rendering, commits follow device success.
   Finish trims any event belonging to an unsubmitted final block. */
int at_take_allocate(AtTake *take,unsigned capacity);
void at_take_free(AtTake *take);
int at_take_begin(AtTake *take,const AdConfig *config,const AdControl *initial);
int at_take_event(AtTake *take,uint64_t frame,const AdControl *actual_control);
int at_take_commit(AtTake *take,unsigned frames,uint64_t output_hash,uint64_t source_hash);
void at_take_finish(AtTake *take);
int at_take_valid(const AtTake *take);
uint64_t at_hash_samples(uint64_t hash,const float *audio,unsigned samples);
/* Frame-interleaved order: DNA raw,L/R; DNA voiced,L/R; residual,L/R;
   body,L/R; event mono; auxiliary10objects; startupL/R; catch delta L/R;
   resonant L/R; coherent LF raw,L/R and output,L/R. All earlier capture pointers
   must be present; NULL optional resonant/LF means zeros. Configured nonzero
   layers must be captured, including LF raw even when its amount is zero.
   Same source hash for stereo and12channel playback. */
uint64_t at_hash_sources(uint64_t hash,const AdCapture *capture,unsigned frames);
const char *at_render_id(void);
#endif
