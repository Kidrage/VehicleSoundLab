#include "engine.h"
#include "modules.h"
#include <math.h>
/* Sparse high firing orders extend beyond the low 720-degree Fourier bank.
   AM, bank phase and load colour remain explicit; no reference samples play. */
void vsl_legacy_high_orders_tick(VslEngine *e,VslObjectFrame *o) {
    static const int orders[]={27,29,31,34,37,41,45,49,54,59,65,72,80,88,98,109,122,136,152,170,190,212,238,266};
    const VslProfile *p=vsl_profile(e->smooth.profile);
    float bank=e->control.rpm*p->cylinders/240,phase=e->control.phase*p->cylinders/2;
    float threshold=e->control.rpm/120*VSL_PARTIALS;
    int c,k;
    if(e->dna.custom_count || e->smooth.profile==VSL_SCIFI || bank<1)return;
    for(c=0;c<2;++c) {
        float out=0,ph=phase+c*VSL_PI;
        for(k=0;k<24;++k) {
            float f=bank*orders[k],band=vsl_clamp((f-threshold)/400,0,1),z;
            if(f>=e->sample_rate*.46f)continue;
            z=logf(fmaxf(f,20)/3900)/.78f;
            band*=expf(-.5f*z*z)*vsl_clamp((e->sample_rate*.46f-f)/(e->sample_rate*.04f),0,1);
            out+=sinf(ph*orders[k]+.15f*sinf(ph))*band*.007f;
        }
        o->sample[VSL_EXHAUST_L+c]+=out*e->voice.high_gain*e->smooth.detail*e->smooth.dna*(.5f+e->smooth.brightness);
    }
}
