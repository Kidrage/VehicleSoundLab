#include "pulse_kernel.h"
#include "profiles/firing_source.h"
#include <math.h>
#include <string.h>
#define PI 3.14159265358979323846f
float vsl_pulse_wavelet(float time,float tau) {
    float u=time/tau;
    if(time<0||u>48)return 0;
    /* Derivative of u^4 exp(-u): zero integral, continuous first/second
       derivatives at onset. Positive peak=1 at u=2; no sample playback. */
    return .46181600618316564f*u*u*u*(4-u)*expf(-u);
}
static float cross_energy(float a,float b) {
    float s=1/a+1/b;
    return .46181600618316564f*.46181600618316564f*
        (16*720/(powf(a,3)*powf(b,3)*powf(s,7))-
         4*5040*(1/(powf(a,3)*powf(b,4))+1/(powf(a,4)*powf(b,3)))/powf(s,8)+
         40320/(powf(a,4)*powf(b,4)*powf(s,9)));
}
float vsl_pulse_kernel_energy(float slow,float fast) {
    float w=vsl_pulse_profile()->fast_weight;
    return (1-w)*(1-w)*cross_energy(slow,slow)+w*w*cross_energy(fast,fast)+
        2*w*(1-w)*cross_energy(slow,fast);
}
int vsl_pulse_kernel_init(VslPulseKernel *s,float rate) {
    float total=0,fc=.38f/VSL_PULSE_OVERSAMPLE;int k;
    if(!s||!isfinite(rate)||rate<16000||rate>192000)return 0;
    memset(s,0,sizeof *s);s->rate=rate;
    for(k=0;k<VSL_PULSE_TAPS;++k) {
        float t=k-(VSL_PULSE_TAPS-1)*.5f;
        float window=.42f-.5f*cosf(2*PI*k/(VSL_PULSE_TAPS-1))+.08f*cosf(4*PI*k/(VSL_PULSE_TAPS-1));
        s->fir[k]=(t==0?2*fc:sinf(2*PI*fc*t)/(PI*t))*window;
        total+=s->fir[k];
    }
    for(k=0;k<VSL_PULSE_TAPS;++k)s->fir[k]/=total;
    return 1;
}
void vsl_pulse_kernel_strike(VslPulseKernel *s,int bank,float elapsed,float gain,float slow,float fast) {
    int i;
    if(bank<0||bank>1||!isfinite(elapsed)||elapsed<0||!isfinite(gain)||
       !isfinite(slow)||!isfinite(fast)||slow<=0||fast<=0)return;
    for(i=0;i<VSL_PULSE_VOICES;++i)if(!s->voices[bank][i].active) {
        VslPulseVoice *v=&s->voices[bank][i];
        v->active=1;v->age=elapsed-1/s->rate;v->gain=gain;v->slow=slow;v->fast=fast;return;
    }
    ++s->overflow; /* Never steal a ringing response silently. */
}
void vsl_pulse_kernel_tick(VslPulseKernel *s,float result[2]) {
    int os,b,i,k;float w=vsl_pulse_profile()->fast_weight,dt=1/(s->rate*VSL_PULSE_OVERSAMPLE);
    for(os=0;os<VSL_PULSE_OVERSAMPLE;++os) {
        for(b=0;b<2;++b) {
            float x=0;
            for(i=0;i<VSL_PULSE_VOICES;++i) {
                VslPulseVoice *v=&s->voices[b][i];if(!v->active)continue;
                v->age+=dt;
                x+=v->gain*((1-w)*vsl_pulse_wavelet(v->age,v->slow)+w*vsl_pulse_wavelet(v->age,v->fast));
                if(v->age>48*fmaxf(v->slow,v->fast))v->active=0;
            }
            s->history[b][s->cursor]=x;
        }
        if(os==VSL_PULSE_OVERSAMPLE-1)for(b=0;b<2;++b) {
            float y=0;
            for(k=0;k<VSL_PULSE_TAPS;++k)y+=s->fir[k]*s->history[b][(s->cursor+VSL_PULSE_TAPS-k)%VSL_PULSE_TAPS];
            result[b]=y;
        }
        s->cursor=(s->cursor+1)%VSL_PULSE_TAPS;
    }
}
