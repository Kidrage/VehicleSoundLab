#ifndef VSL_LAYER_MONITOR_LISTEN_H
#define VSL_LAYER_MONITOR_LISTEN_H
#include "layers.h"
#define LM_RAMP_FRAMES 864u /*18ms at the host's48kHz. */
typedef struct {
    double weight[LM_SELECTIONS],step[LM_SELECTIONS];
    unsigned remaining;
    int selection;
} LmListen;
int lm_selection_valid(int selection);
int lm_listen_init(LmListen *state,int selection);
int lm_listen_set(LmListen *state,int selection);
/* pcm is canonical full stereo on entry, monitored stereo on return.
   layers is frame-major [six buses][L,R], after master AND transport fade.
   No source access/reset, allocation, I/O, room or per-bus normalization. */
int lm_listen_process(LmListen *state,float *pcm,const float *layers,unsigned frames);
#endif
