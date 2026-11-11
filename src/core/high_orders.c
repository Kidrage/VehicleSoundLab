#include "engine.h"
#include "modules.h"
#include "profiles/high_orders.h"
#include "profiles/firing.h"
#include "exhaust_spectrum.h"
#include <math.h>
#include <string.h>

static double rise(double x) { x=vsl_clamp(x,0,1);return x*x*(3-2*x); }
void vsl_high_orders_update(VslEngine *e) {
    const VslHighOrderProfile *shape=vsl_high_order_profile(e->smooth.profile);
    const VslProfile *p=vsl_profile(e->smooth.profile);
    double bank=e->control.rpm*p->cylinders/240;
    int n,c,last=0;
    if(!shape || e->dna.custom_count) { memset(&e->high_orders,0,sizeof e->high_orders);return; }
    for(n=1;n<=VSL_HIGH_ORDERS;++n) {
        double value=0;
        int index=n-VSL_CONTINUATION_FIRST;
        if(index>=0 && index<VSL_CONTINUATION_COUNT)
            for(c=0;c<2;++c)e->high_orders.continuation_target[c][index]=0;
        if(bank>=1) {
            double f=bank*n,threshold=e->control.rpm/120*VSL_PARTIALS;
            double z=log(fmax(f,20)/shape->center_hz)/shape->log_width;
            double nyquist_guard=rise((e->sample_rate*.46-f*e->combustion.stretch)/(e->sample_rate*.04));
            double upper=rise((shape->upper_hz-f)/1200);
            double boundary=threshold/bank;
            double blend=rise((n-boundary)/(shape->continuation_end_order-boundary));
            if(n>=VSL_CONTINUATION_FIRST) {
                value=shape->level*sqrt(bank/shape->density_reference_hz)*exp(-.5*z*z)*upper*blend*nyquist_guard;
                if(index<VSL_CONTINUATION_COUNT)for(c=0;c<2;++c)
                    e->high_orders.continuation_target[c][index]=vsl_exhaust_continuation(e,n,c)*(1-blend)*upper*nyquist_guard;
            }
        }
        e->high_orders.target[n-1]=value;
        if(value>1e-12 || e->high_orders.amplitude[n-1]>1e-12)last=n;
        if(index>=0 && index<VSL_CONTINUATION_COUNT)for(c=0;c<2;++c)
            if(e->high_orders.continuation_target[c][index]>1e-12 || e->high_orders.continuation[c][index]>1e-12)last=n;
    }
    e->high_orders.active=last;
}
void vsl_high_orders_tick(VslEngine *e,VslObjectFrame *o) {
    const VslProfile *p=vsl_profile(e->smooth.profile);
    double bank=e->control.rpm*p->cylinders/240;
    double phase=e->control.phase*p->cylinders/2;
    double phase_r=phase-2*VSL_PI*vsl_bank_offset_cycles(e->smooth.profile)-2*VSL_PI*bank*p->bank_delay;
    phase+=e->combustion.phase_delta[0]*p->cylinders/2;
    phase_r+=e->combustion.phase_delta[1]*p->cylinders/2;
    double cl=cos(phase),sl=sin(phase),cr=cos(phase_r),sr=sin(phase_r);
    double c_l=cl,s_l=sl,c_r=cr,s_r=sr,left=0,right=0,continued_left=0,continued_right=0;
    double slew=1-exp(-1/(.008*e->sample_rate));
    int n;
    if(e->dna.custom_count || e->smooth.profile==VSL_SCIFI || bank<1)return;
    if(!vsl_high_order_profile(e->smooth.profile)) { vsl_legacy_high_orders_tick(e,o);return; }
    /* Both banks use the same combustion clock. Right phase has the same
       common-pin bank geometry and delay in seconds as the low DNA bank.
       No arbitrary channel detune or independent peak selection is used. */
    for(n=1;n<=e->high_orders.active;++n) {
        double next,f=bank*n;
        double guard=rise((e->sample_rate*.46-f*e->combustion.stretch)/(e->sample_rate*.04));
        double amplitude=e->high_orders.amplitude[n-1]+slew*(e->high_orders.target[n-1]-e->high_orders.amplitude[n-1]);
        e->high_orders.amplitude[n-1]=amplitude;
        left+=amplitude*c_l*guard;right+=amplitude*c_r*guard;
        if(n>=VSL_CONTINUATION_FIRST && n<=VSL_CONTINUATION_LAST) {
            int index=n-VSL_CONTINUATION_FIRST;
            double *l=&e->high_orders.continuation[0][index],*r=&e->high_orders.continuation[1][index];
            *l+=slew*(e->high_orders.continuation_target[0][index]-*l);
            *r+=slew*(e->high_orders.continuation_target[1][index]-*r);
            continued_left+=*l*c_l*guard;continued_right+=*r*c_r*guard;
        }
        next=s_l*cl+c_l*sl;c_l=c_l*cl-s_l*sl;s_l=next;
        next=s_r*cr+c_r*sr;c_r=c_r*cr-s_r*sr;s_r=next;
    }
    {
        double gain=e->voice.high_gain*e->smooth.detail*e->smooth.dna*(.5+e->smooth.brightness);
        /* Near the partition, continue the actual DNA source amplitude. Farther
           above it, retain the independently controlled high-detail curve. At
           default detail, the first missing orders have the same gain law as
           low DNA; zero detail still removes the entire upper extension. */
        double continuation_gain=.65*e->voice.dna_gain*e->smooth.dna*
            e->smooth.detail/vsl_high_order_profile(e->smooth.profile)->reference_detail;
        o->sample[VSL_EXHAUST_L]+=(left*gain+continued_left*continuation_gain)*e->combustion.gain[0];
        o->sample[VSL_EXHAUST_R]+=(right*gain+continued_right*continuation_gain)*e->combustion.gain[1];
    }
}
