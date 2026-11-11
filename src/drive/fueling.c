#include "fueling.h"
#include "core/engine.h"
#include "profiles/fueling.h"
#include <math.h>

int vsl_fueling_allows_firing(const VslDrive *d) {
    return (d->lifecycle==VSL_RUNNING||d->lifecycle==VSL_CATCH)&&
        d->combustion>0&&d->fuel.command>0;
}

const char *vsl_fuel_mode_name(VslFuelMode mode) {
    static const char *names[]={"OFF","FIRE","DELAY","CUT","RESUME"};
    return names[mode>=VSL_FUEL_OFF&&mode<=VSL_FUEL_RESUME?mode:0];
}
void vsl_fueling_step(VslDrive *d,const VslParams *params,double dt) {
    VslFuel *f=&d->fuel;
    const VslFuelingProfile *p=vsl_fueling_profile(d->profile);
    double idle=vsl_profile(d->profile)->idle_rpm;
    int enabled=params->fuel_cut && params->profile!=VSL_SCIFI;
    int reopen=d->engine_throttle>=p->reopen_pedal || d->blip>0 ||
        d->rpm<=idle+p->resume_above_idle || d->load>=-.01 || !enabled;
    if(d->lifecycle!=VSL_RUNNING) {
        f->closed_seconds=f->resume_seconds=0;
        f->command=d->lifecycle==VSL_CATCH?1:0;
        f->mode=f->command?VSL_FUEL_FIRE:VSL_FUEL_OFF;return;
    }
    if(f->mode==VSL_FUEL_CUT) {
        if(!reopen) { f->command=0;return; }
        f->mode=VSL_FUEL_RESUME;f->resume_seconds=0;f->closed_seconds=0;
    }
    f->command=1;
    if(f->mode==VSL_FUEL_RESUME) {
        f->resume_seconds+=dt;
        if(f->resume_seconds<p->resume_hold)return;
        f->mode=VSL_FUEL_FIRE;
    }
    if(enabled && !reopen && d->rpm>=idle+p->enter_above_idle &&
       d->engine_throttle<=p->close_pedal) {
        double delay=d->gear?p->coupled_delay:p->neutral_delay;
        f->closed_seconds+=dt;f->mode=VSL_FUEL_DELAY;
        if(f->closed_seconds+1e-12>=delay) { f->mode=VSL_FUEL_CUT;f->command=0; }
    } else { f->closed_seconds=0;f->mode=VSL_FUEL_FIRE; }
}
