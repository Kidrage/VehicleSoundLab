#include "engine.h"
#include "modules.h"
#include <math.h>
/* Retain the old carrier voice for an explicit comparison. Modal excitation
   and data live separately; intake remains unchanged in this iteration. */
void vsl_mechanical_tick(VslEngine *e,VslObjectFrame *o) {
    const VslProfile *p=vsl_profile(e->smooth.profile);
    float bank=e->control.rpm*p->cylinders/240,phase=e->control.phase*p->cylinders/2;
    float legacy=0,modal;
    int c;
    modal=vsl_mechanical_modal_tick(e)*e->smooth.mechanical*e->smooth.noise;
    if(e->smooth.profile==VSL_SCIFI)return;
    for(c=0;bank>=1 && c<2;++c) {
        float f=c?3100.f:1760.f;
        if(f<e->sample_rate*.40f) {
            e->detail.metal[c]=fmodf(e->detail.metal[c]+2*VSL_PI*f/e->sample_rate,2*VSL_PI);

            /* Keep legacy phases advancing; at exact mix=1 its contribution
               is zero. It resumes from the same state if the mix changes. */
            if(e->mechanical.mix!=1)

            legacy+=sinf(e->detail.metal[c])*(.4f+.6f*powf(.5f+.5f*cosf(phase),4))*e->voice.mechanical_gain*e->smooth.mechanical*e->smooth.noise*.11f;
        }
    }
    o->sample[VSL_MECHANICAL]+=legacy*(1-e->mechanical.mix)+modal*e->mechanical.mix;
    if(bank>=1&&e->voice.intake_gain!=0)o->sample[VSL_INTAKE]+=sinf(phase*2)*e->voice.intake_gain*e->smooth.intake*.14f;
}
