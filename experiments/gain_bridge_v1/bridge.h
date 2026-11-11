#ifndef VSL_GAIN_BRIDGE_H
#define VSL_GAIN_BRIDGE_H
#include "core/engine.h"
#include "session/take.h"
#define VSL_BRIDGE_GAINS 7
typedef struct {
    double current[VSL_BRIDGE_GAINS],start[VSL_BRIDGE_GAINS],target[VSL_BRIDGE_GAINS];
    double previous_held[VSL_BRIDGE_GAINS],previous_ramp[VSL_BRIDGE_GAINS];
    double maximum_held_step[VSL_BRIDGE_GAINS],maximum_ramp_step[VSL_BRIDGE_GAINS];
    unsigned period,position;
    int enabled;
} VslGainBridge;
int vsl_gain_bridge_init(VslGainBridge *bridge,int enabled);
int vsl_gain_bridge_control(VslGainBridge *bridge,const VslVoicing *voice,unsigned period);
void vsl_gain_bridge_audio(VslGainBridge *bridge,VslVoicing *voice,float *gain_pairs);
const char *vsl_gain_bridge_name(int index);
int vsl_gain_bridge_process(VslEngine *e,VslGainBridge *bridge,float *out,
    unsigned frames,int channels,float *stems,float *gain_pairs);
unsigned vsl_gain_bridge_take(VslTakePlayer *player,VslEngine *e,VslGainBridge *bridge,
    float *out,unsigned frames,int channels,float *stems,float *gain_pairs);
#endif
