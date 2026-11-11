#ifndef VSL_EVENT_COLOR_H
#define VSL_EVENT_COLOR_H
#include "split.h"
#include "core/engine.h"
#include "session/take.h"
typedef struct {
    VslColorLowpass low[2][2];
    double rate,amount,follow,target[2][2],smooth[2][2],history[2][128];
    double last[8],max_mod;
    unsigned seen[10],cursor;int eligible;
    uint64_t events[2],denied_events;
    /* Optional offline double-precision observer; no allocation or file I/O. */
    double *tap_samples;uint64_t tap_frames,tap_capacity;
} VslEventColor;
int vsl_color_init(VslEventColor *s,double rate,double amount);
void vsl_color_tick(VslEventColor *s,const VslEngine *e,VslObjectFrame *o,const double main_pressure[2]);
int vsl_color_process(VslEngine *e,VslEventColor *s,float *out,unsigned frames,int channels,float *stems);
unsigned vsl_color_take(VslTakePlayer *player,VslEngine *e,VslEventColor *s,float *out,unsigned frames,int channels,float *stems);
#endif
