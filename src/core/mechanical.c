#include "engine.h"
#include "modules.h"
#include <math.h>
/* Retain the old carrier voice for an explicit comparison. Modal excitation
   and data live separately; intake remains unchanged in this iteration. */
void vsl_mechanical_tick(VslEngine *e,VslObjectFrame *o) {
    const VslProfile *p=vsl_profile(e->smooth.profile);
    double bank=e->control.rpm*p->cylinders/240,phase=e->control.phase*p->cylinders/2;
    double legacy=0,modal;
    int c;
    modal=vsl_mechanical_modal_tick(e)*e->smooth.mechanical*e->smooth.noise;
    if(e->smooth.profile==VSL_SCIFI)return;
    for(c=0;bank>=1 && c<2;++c) {
        double f=c?3100:1760;
        if(f<e->sample_rate*.40) {
            e->detail.metal[c]=fmod(e->detail.metal[c]+2*VSL_PI*f/e->sample_rate,2*VSL_PI);
            legacy+=sin(e->detail.metal[c])*(.4+.6*pow(.5+.5*cos(phase),4))*e->voice.mechanical_gain*e->smooth.mechanical*e->smooth.noise*.11;
        }
    }
    o->sample[VSL_MECHANICAL]+=legacy*(1-e->mechanical.mix)+modal*e->mechanical.mix;
    if(bank>=1)o->sample[VSL_INTAKE]+=sin(phase*2)*e->voice.intake_gain*e->smooth.intake*.14;
}
