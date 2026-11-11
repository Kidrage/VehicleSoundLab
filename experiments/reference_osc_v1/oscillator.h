#ifndef VSL_REFERENCE_OSCILLATOR_H
#define VSL_REFERENCE_OSCILLATOR_H
#include "model.h"
typedef struct {
    const RoModel *model;uint64_t frame;unsigned segment;
    double high_amount,high_target,follow;
} RoPlayer;
int ro_player_init(RoPlayer *player,const RoModel *model,double high_amount);
int ro_set_high(RoPlayer *player,double high_amount);
/* No allocation, file I/O, RNG, reference waveform or engine-event generator. */
unsigned ro_process(RoPlayer *player,double *stereo,double *high_stereo,unsigned frames);
#endif
