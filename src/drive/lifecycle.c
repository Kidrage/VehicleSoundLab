#include "lifecycle.h"
#include "shift.h"
#include "core/engine.h"
#include "core/modules.h"
#include "profiles/lifecycle.h"
#include <math.h>

static double ease(double x) { x=vsl_clamp(x,0,1);return x*x*(3-2*x); }
static void enter(VslDrive *d,VslLifecycle state) {
    d->lifecycle=state;d->life_seconds=0;
    d->life_entry_rpm=d->rpm;d->life_entry_rate=d->rpm_rate;
}
const char *vsl_lifecycle_name(VslLifecycle state) {
    static const char *names[]={"OFF","READY","CRANK","CATCH","RUNNING","STOPPING"};
    return names[state>=VSL_OFF&&state<=VSL_STOPPING?state:0];
}
int vsl_lifecycle_step(VslDrive *d,const VslParams *params,double dt) {
    const VslLifecycleProfile *p=vsl_lifecycle_profile(params->profile);
    double idle=vsl_profile(params->profile)->idle_rpm,old_rpm=d->rpm;
    int old_start=d->last_start;
    d->last_start=params->start_id;d->life_seconds+=dt;d->lifecycle_flare=0;
    if(!params->ignition && d->lifecycle!=VSL_OFF && d->lifecycle!=VSL_STOPPING) {
        enter(d,VSL_STOPPING);vsl_shift_cancel(d);
        d->overrun_armed=0;d->armed_seconds=0;d->release_seconds=-1;
    }
    if(params->ignition && d->lifecycle==VSL_OFF)enter(d,VSL_READY);
    if(params->ignition && params->start_id!=old_start && d->lifecycle==VSL_READY) {
        enter(d,VSL_CRANK);d->running_seconds=0;++d->start_events;
    }
    if(d->lifecycle==VSL_CRANK && d->life_seconds+1e-12>=p->crank_seconds)enter(d,VSL_CATCH);
    if(d->lifecycle==VSL_CATCH && d->life_seconds+1e-12>=p->catch_rise_seconds+p->catch_settle_seconds)enter(d,VSL_RUNNING);
    if(d->lifecycle==VSL_STOPPING && d->life_seconds+1e-12>=p->stopping_seconds)enter(d,VSL_OFF);
    if(d->lifecycle==VSL_RUNNING) { d->combustion=1;return 1; }
    d->combustion=0;
    if(d->lifecycle==VSL_CRANK) {
        d->rpm=p->crank_rpm*(1-exp(-d->life_seconds/p->crank_tau));
    } else if(d->lifecycle==VSL_CATCH) {
        double peak=fmax(idle,p->flare_rpm),t=d->life_seconds;
        if(t<p->catch_rise_seconds) {
            double u=vsl_clamp(t/p->catch_rise_seconds,0,1);
            /* Hermite rise retains entry speed AND entry slope; zero slope at
               flare peak. Bound tangent to preserve a monotone rise even if a
               future profile supplies a steep starter acceleration. */
            double tangent=vsl_clamp(d->life_entry_rate*p->catch_rise_seconds,0,
                fmax(0,3*(peak-d->life_entry_rpm)));
            d->rpm=d->life_entry_rpm+(peak-d->life_entry_rpm)*ease(u)+tangent*u*(1-u)*(1-u);
            d->lifecycle_flare=ease(u);
        } else {
            d->lifecycle_flare=1-ease((t-p->catch_rise_seconds)/p->catch_settle_seconds);
            d->rpm=idle+(peak-idle)*d->lifecycle_flare;
        }
        d->combustion=ease(t/p->combustion_seconds);
    } else if(d->lifecycle==VSL_STOPPING) {
        d->rpm*=exp(-dt/p->stopping_tau);
    } else d->rpm=0;
    d->previous_rpm=old_rpm;d->rpm_rate=(d->rpm-old_rpm)/dt;
    return 0;
}
