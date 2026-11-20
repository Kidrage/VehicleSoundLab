#ifndef VSL_PARTITIONED_FIR_FILTER_H
#define VSL_PARTITIONED_FIR_FILTER_H
#include "fft.h"
#define PF_MAX_TAPS 512
typedef struct PfKernel PfKernel;
typedef struct PfState PfState;
/* Non-RT allocation/FFT compile, immutable owned kernel. Finite |tap|<=64.
   State borrows the kernel, which must outlive it. Free only outside audio. */
PfKernel *pf_kernel_create(const float *taps,unsigned count);
void pf_kernel_destroy(PfKernel *kernel);
PfState *pf_state_create(const PfKernel *kernel);
void pf_state_destroy(PfState *state);
/* RT causal FIR: consumes/returns exactly64 samples. Input/output may alias.
   Finite |input|<=1e20 checked before mutation. No allocation/IO. Block API
   requires the complete input block; it is not a zero-latency external filter.
   VSL_DSP_STATIC shares FFT scratch: serialize all FIR calls (no reentrancy). */
int pf_filter_block(PfState *state,const float input[PF_BLOCK],float output[PF_BLOCK]);
#endif
