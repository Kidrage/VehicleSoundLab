#ifndef VSL_FINE_IDLE_LAYER_STATE_H
#define VSL_FINE_IDLE_LAYER_STATE_H
#include "profile.h"
#include <stdint.h>
typedef struct FiState FiState;
typedef struct {float modal[2],detail[2],raw[2],output[2],weight,keep;} FiFrame;
/* Non-RT allocation/compile/prewarm; immutable profiles must outlive state.
   Destroy before replacing the state or releasing profiles. No audio-time IO. */
FiState *fi_state_create(const FiProfile *profile,uint64_t seed,float amount,float motion,float detail);
void fi_state_destroy(FiState *state);
/* RT all sources always advance. Gate is external, amount0..1 follows18ms;
   core motion and detail amount use finite18ms ramps. No driver/RPM clock. */
int fi_state_tick(FiState *state,int gate,float amount,float motion,float detail,float envelope,FiFrame *frame);
#endif
