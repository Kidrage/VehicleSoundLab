#ifndef VSL_MODAL_LAYER_STATE_H
#define VSL_MODAL_LAYER_STATE_H
#include "voice.h"
typedef struct { MlVoice voice;double amount,follow; } MlState;
/* Non-RT. The caller supplies the gate; this module has no driver or RPM clock.
   Profile and nested source storage remain immutable at their original address. */
int ml_state_init(MlState *state,const MlProfile *profile,uint64_t seed,double amount);
/* RT. Keeps oscillator/filter/RNG advancing at gate0 or amount0. The external
   amount follows over18ms; the profile's finite gate ramp is independent. */
int ml_state_tick(MlState *state,int gate,double amount,double envelope,MlFrame *frame);
#endif
