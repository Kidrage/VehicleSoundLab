#ifndef VSL_PARTITIONED_FIR_MAC_H
#define VSL_PARTITIONED_FIR_MAC_H
#include "partitioned_fir/fft.h"
/* Internal complex multiply/add, preserves per-bin scalar operation order.
   Distinct arrays of PF_FFT values; no allocation or data-dependent dispatch. */
void pf_mac_add(PfComplex sum[PF_FFT],const PfComplex x[PF_FFT],const PfComplex h[PF_FFT]);
const char *pf_mac_backend(void);
#endif
