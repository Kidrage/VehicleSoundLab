#ifndef VSL_EXPERIMENT_PHASE_TRANSFER_H
#define VSL_EXPERIMENT_PHASE_TRANSFER_H
#include "allpass.h"
#include "core/engine.h"
#include "session/take.h"
typedef struct {
    VslAllpass bank[2][3];double delay[2][256],sample_rate;
    unsigned cursor,delay_samples;int mode,eligible;
} VslExhaustTransfer;
int vsl_phase_init(VslExhaustTransfer *s,double rate,int mode);
void vsl_phase_tick(VslExhaustTransfer *s,VslEngine *e,VslObjectFrame *objects);
int vsl_phase_process_layout(VslEngine *e,VslExhaustTransfer *transfer,float *out,unsigned frames,int channels,float *stems);
unsigned vsl_phase_take_process(VslTakePlayer *player,VslEngine *e,VslExhaustTransfer *transfer,float *out,unsigned frames,int channels,float *stems);
#endif
