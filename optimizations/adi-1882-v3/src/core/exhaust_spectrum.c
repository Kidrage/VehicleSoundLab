#include "exhaust_spectrum.h"
#include "engine.h"
#include <math.h>
static float bell(float f,float center,float width) {
    float d=logf(f/center)/width;return expf(-.5f*d*d);
}
float vsl_exhaust_envelope(const VslEngine *e,float order,float f) {
    const VslProfile *p=vsl_profile(e->smooth.profile);
    float envelope=powf(fmaxf(.25f,order/p->cylinders),-(p->tilt+e->voice.tilt_delta))*
        (.14f+.85f*bell(f,p->formant[0],p->formant_width[0])+
         (.35f+.65f*e->voice.pull)*bell(f,p->formant[1],p->formant_width[1])+
         (.08f+.95f*e->voice.pull)*bell(f,p->formant[2],p->formant_width[2]));
    envelope*=expf(-f/((1700+e->smooth.brightness*8500+e->voice.pull*3000)*fmaxf(.4f,e->voice.cutoff_ratio)));
    envelope*=1+.12f*e->voice.idle*bell(f,120,.65f)-.2f*e->voice.overrun*bell(f,3500,.6f);
    return envelope;
}
float vsl_exhaust_continuation(const VslEngine *e,int order,int side) {
    const VslProfile *p=vsl_profile(e->smooth.profile);
    float weight=0,cycle_order=order*p->cylinders/2.0f;
    float f=e->control.rpm/120.0f*cycle_order;int c;
    if(e->smooth.profile!=VSL_V10 || e->dna.custom_count || f<=0)return 0;
    /* Every integer bank harmonic has the same sum of cylinder weights as
       low DNA. Right-bank geometry/delay is applied by the oscillator phase,
       not by identifying the recording R channel with the right engine bank. */
    for(c=0;c<p->cylinders;++c)if(p->bank[c]==side)
        weight+=2*(1+.045f*sinf(1.7f*c))/p->cylinders;
    return vsl_exhaust_envelope(e,cycle_order,f)*weight*e->dna.factory_scale;
}
