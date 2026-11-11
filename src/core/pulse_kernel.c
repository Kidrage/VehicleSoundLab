#include "pulse_kernel.h"
#include "profiles/firing_source.h"
#include <math.h>
#include <string.h>
#define PI 3.14159265358979323846
double vsl_pulse_wavelet(double time,double tau) {
    double u=time/tau;
    if(time<0||u>48)return 0;
    /* Derivative of u^4 exp(-u): zero integral, continuous first/second
       derivatives at onset. Positive peak=1 at u=2; no sample playback. */
    return .46181600618316564*u*u*u*(4-u)*exp(-u);
}
static double cross_energy(double a,double b) {
    double s=1/a+1/b;
    return .46181600618316564*.46181600618316564*
        (16*720/(pow(a,3)*pow(b,3)*pow(s,7))-
         4*5040*(1/(pow(a,3)*pow(b,4))+1/(pow(a,4)*pow(b,3)))/pow(s,8)+
         40320/(pow(a,4)*pow(b,4)*pow(s,9)));
}
double vsl_pulse_kernel_energy(double slow,double fast) {
    double w=vsl_pulse_profile()->fast_weight;
    return (1-w)*(1-w)*cross_energy(slow,slow)+w*w*cross_energy(fast,fast)+
        2*w*(1-w)*cross_energy(slow,fast);
}
int vsl_pulse_kernel_init(VslPulseKernel *s,double rate) {
    double total=0,fc=.38/VSL_PULSE_OVERSAMPLE;int k;
    if(!s||!isfinite(rate)||rate<16000||rate>192000)return 0;
    memset(s,0,sizeof *s);s->rate=rate;
    for(k=0;k<VSL_PULSE_TAPS;++k) {
        double t=k-(VSL_PULSE_TAPS-1)*.5;
        double window=.42-.5*cos(2*PI*k/(VSL_PULSE_TAPS-1))+.08*cos(4*PI*k/(VSL_PULSE_TAPS-1));
        s->fir[k]=(t==0?2*fc:sin(2*PI*fc*t)/(PI*t))*window;
        total+=s->fir[k];
    }
    for(k=0;k<VSL_PULSE_TAPS;++k)s->fir[k]/=total;
    return 1;
}
void vsl_pulse_kernel_strike(VslPulseKernel *s,int bank,double elapsed,double gain,double slow,double fast) {
    int i;
    if(bank<0||bank>1||!isfinite(elapsed)||elapsed<0||!isfinite(gain)||
       !isfinite(slow)||!isfinite(fast)||slow<=0||fast<=0)return;
    for(i=0;i<VSL_PULSE_VOICES;++i)if(!s->voices[bank][i].active) {
        VslPulseVoice *v=&s->voices[bank][i];
        v->active=1;v->age=elapsed-1/s->rate;v->gain=gain;v->slow=slow;v->fast=fast;return;
    }
    ++s->overflow; /* Never steal a ringing response silently. */
}
void vsl_pulse_kernel_tick(VslPulseKernel *s,double result[2]) {
    int os,b,i,k;double w=vsl_pulse_profile()->fast_weight,dt=1/(s->rate*VSL_PULSE_OVERSAMPLE);
    for(os=0;os<VSL_PULSE_OVERSAMPLE;++os) {
        for(b=0;b<2;++b) {
            double x=0;
            for(i=0;i<VSL_PULSE_VOICES;++i) {
                VslPulseVoice *v=&s->voices[b][i];if(!v->active)continue;
                v->age+=dt;
                x+=v->gain*((1-w)*vsl_pulse_wavelet(v->age,v->slow)+w*vsl_pulse_wavelet(v->age,v->fast));
                if(v->age>48*fmax(v->slow,v->fast))v->active=0;
            }
            s->history[b][s->cursor]=x;
        }
        if(os==VSL_PULSE_OVERSAMPLE-1)for(b=0;b<2;++b) {
            double y=0;
            for(k=0;k<VSL_PULSE_TAPS;++k)y+=s->fir[k]*s->history[b][(s->cursor+VSL_PULSE_TAPS-k)%VSL_PULSE_TAPS];
            result[b]=y;
        }
        s->cursor=(s->cursor+1)%VSL_PULSE_TAPS;
    }
}
