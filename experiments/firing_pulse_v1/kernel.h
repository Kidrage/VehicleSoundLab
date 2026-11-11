#ifndef VSL_FIRING_PULSE_KERNEL_H
#define VSL_FIRING_PULSE_KERNEL_H
#define FP_OVERSAMPLE 4
#define FP_TAPS 97
#define FP_VOICES 16
typedef struct { double age,gain,slow,fast;int active; } FpVoice;
typedef struct {
    double rate,fir[FP_TAPS],history[2][FP_TAPS];
    unsigned cursor,overflow;
    FpVoice voices[2][FP_VOICES];
} FpKernel;
double fp_wavelet(double time,double tau);
double fp_kernel_energy(double slow,double fast);
int fp_kernel_init(FpKernel *s,double rate);
void fp_kernel_strike(FpKernel *s,int bank,double elapsed,double gain,double slow,double fast);
void fp_kernel_tick(FpKernel *s,double result[2]);
#endif
