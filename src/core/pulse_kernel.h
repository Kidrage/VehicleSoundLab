#ifndef VSL_PULSE_KERNEL_H
#define VSL_PULSE_KERNEL_H
#define VSL_PULSE_OVERSAMPLE 4
#define VSL_PULSE_TAPS 97
#define VSL_PULSE_VOICES 16
typedef struct { double age,gain,slow,fast;int active; } VslPulseVoice;
typedef struct {
    double rate,fir[VSL_PULSE_TAPS],history[2][VSL_PULSE_TAPS];
    unsigned cursor,overflow;
    VslPulseVoice voices[2][VSL_PULSE_VOICES];
} VslPulseKernel;
double vsl_pulse_wavelet(double time,double tau);
double vsl_pulse_kernel_energy(double slow,double fast);
int vsl_pulse_kernel_init(VslPulseKernel *s,double rate);
void vsl_pulse_kernel_strike(VslPulseKernel *s,int bank,double elapsed,double gain,double slow,double fast);
void vsl_pulse_kernel_tick(VslPulseKernel *s,double result[2]);
#endif
