#ifndef VSL_PULSE_KERNEL_H
#define VSL_PULSE_KERNEL_H
#define VSL_PULSE_OVERSAMPLE 4
#define VSL_PULSE_TAPS 97
#define VSL_PULSE_VOICES 16
typedef struct { float age,gain,slow,fast;int active; } VslPulseVoice;
typedef struct {
    float rate,fir[VSL_PULSE_TAPS],history[2][VSL_PULSE_TAPS];
    unsigned cursor,overflow;
    VslPulseVoice voices[2][VSL_PULSE_VOICES];
} VslPulseKernel;
float vsl_pulse_wavelet(float time,float tau);
float vsl_pulse_kernel_energy(float slow,float fast);
int vsl_pulse_kernel_init(VslPulseKernel *s,float rate);
void vsl_pulse_kernel_strike(VslPulseKernel *s,int bank,float elapsed,float gain,float slow,float fast);
void vsl_pulse_kernel_tick(VslPulseKernel *s,float result[2]);
#endif
