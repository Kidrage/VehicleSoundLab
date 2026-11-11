#ifndef VSL_REFERENCE_OSC_PITCH_H
#define VSL_REFERENCE_OSC_PITCH_H
#include "tracks.h"
typedef struct {
    const RoModel *model;const RtTracks *tracks;double *phase_extra;
    uint64_t frame;unsigned segment;
    double pitch,pitch_target,high,high_target,follow;
} RtPlayer;
/* Zero-initialize before first init; model and track IDs remain borrowed.
   Pitch is a relative frequency ratio, never a measured RPM. */
int rt_player_init(RtPlayer *player,const RoModel *model,const RtTracks *tracks,double pitch,double high);
void rt_player_free(RtPlayer *player);
int rt_set(RtPlayer *player,double pitch,double high);
/* No allocation, I/O, RNG, waveform playback or event triggering. */
unsigned rt_process(RtPlayer *player,double *stereo,unsigned frames);
#endif
