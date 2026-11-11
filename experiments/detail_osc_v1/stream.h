#ifndef VSL_DETAIL_STREAM_H
#define VSL_DETAIL_STREAM_H
#include "model.h"
typedef struct {
    const DoModel *model;
    double position,pitch,pitch_target,gain,gain_target,follow;
    uint64_t frame,loops;
    int loop;
} DePlayer;
/* Borrow immutable coefficients. No source waveform, allocation, I/O or RNG
   in processing. Relative varispeed changes pitch and source duration together. */
int de_init(DePlayer *player,const DoModel *model,double pitch,double gain,int loop);
int de_set(DePlayer *player,double pitch,double gain,int loop);
unsigned de_process(DePlayer *player,double *mono,unsigned frames);
#endif
