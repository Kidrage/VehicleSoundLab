#ifndef VSL_FIRING_PULSE_ADAPTER_H
#define VSL_FIRING_PULSE_ADAPTER_H
#include "kernel.h"
#include "core/engine.h"
#include "core/event_split.h"
#include "session/take.h"
typedef struct {
    FpKernel kernel;
    VslColorLowpass legacy_low[2],pulse_low[2];
    unsigned previous[10];
    uint64_t accepted[2],denied;
    double delay[128],last[6],max_delta;
    unsigned cursor;
    int mode,eligible;
} FpAdapter;
int fp_init(FpAdapter *s,double rate,int mode);
void fp_tick(FpAdapter *s,const VslEngine *e,VslObjectFrame *o,const double main_pressure[2]);
int fp_process(VslEngine *e,FpAdapter *s,float *out,unsigned frames,int channels,float *stems);
unsigned fp_take(VslTakePlayer *player,VslEngine *e,FpAdapter *s,float *out,unsigned frames,int channels,float *stems);
#endif
