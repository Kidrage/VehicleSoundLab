#include "exhaust_spectrum.h"
#include "engine.h"
#include <math.h>
static double bell(double f,double center,double width) {
    double d=log(f/center)/width;return exp(-.5*d*d);
}
double vsl_exhaust_envelope(const VslEngine *e,double order,double f) {
    const VslProfile *p=vsl_profile(e->smooth.profile);
    double envelope=pow(fmax(.25,order/p->cylinders),-(p->tilt+e->voice.tilt_delta))*
        (.14+.85*bell(f,p->formant[0],p->formant_width[0])+
         (.35+.65*e->voice.pull)*bell(f,p->formant[1],p->formant_width[1])+
         (.08+.95*e->voice.pull)*bell(f,p->formant[2],p->formant_width[2]));
    envelope*=exp(-f/((1700+e->smooth.brightness*8500+e->voice.pull*3000)*fmax(.4,e->voice.cutoff_ratio)));
    envelope*=1+.12*e->voice.idle*bell(f,120,.65)-.2*e->voice.overrun*bell(f,3500,.6);
    return envelope;
}
double vsl_exhaust_continuation(const VslEngine *e,int order,int side) {
    const VslProfile *p=vsl_profile(e->smooth.profile);
    double weight=0,cycle_order=order*p->cylinders/2.0;
    double f=e->control.rpm/120.0*cycle_order;int c;
    if(e->smooth.profile!=VSL_V10 || e->dna.custom_count || f<=0)return 0;
    /* Every integer bank harmonic has the same sum of cylinder weights as
       low DNA. Right-bank geometry/delay is applied by the oscillator phase,
       not by identifying the recording R channel with the right engine bank. */
    for(c=0;c<p->cylinders;++c)if(p->bank[c]==side)
        weight+=2*(1+.045*sin(1.7*c))/p->cylinders;
    return vsl_exhaust_envelope(e,cycle_order,f)*weight*e->dna.factory_scale;
}
