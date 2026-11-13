#ifndef VSL_PARTITIONED_FIR_FFT_H
#define VSL_PARTITIONED_FIR_FFT_H
#define PF_BLOCK 256
#define PF_FFT (2*PF_BLOCK)
typedef struct {double re,im;} PfComplex;
typedef struct {unsigned reverse[PF_FFT];PfComplex root[PF_FFT/2];} PfFft;
/* Non-RT plan construction; transform itself is allocation-free, in place. */
void pf_fft_init(PfFft *plan);
void pf_fft(const PfFft *plan,PfComplex values[PF_FFT],int inverse);
#endif
