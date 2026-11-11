#include "motion.h"
#include "core/modules.h"
#include "drive/fueling.h"
#include "profiles/fueling.h"
#include <math.h>

void da_motion_tick(VslEngine *e,double follow) {
    const VslFuelingProfile *p=vsl_fueling_profile(e->target.profile);
    double command=vsl_fueling_allows_firing(&e->drive)?1:0;
    double seconds=command>e->excitation.firing?p->attack_seconds:p->release_seconds;
    e->control.rpm+=follow*(e->drive.rpm-e->control.rpm);
    e->control.load+=follow*(e->drive.load-e->control.load);
    e->control.throttle=e->drive.engine_throttle;
    e->control.throttle_delta=e->drive.engine_throttle_rate;
    e->control.acceleration=e->drive.acceleration;
    /* Physical720-degree cycle; never retime the independent acoustic atlas. */
    vsl_clocks_tick(e);
    /* Mechanical resonators read this envelope plus strict firing permission.
       No call to excitation_tick: it would alter the atlas exhaust signal. */
    e->excitation.firing+=(1-exp(-1/(seconds*e->sample_rate)))*(command-e->excitation.firing);
    if(fabs(e->excitation.firing-command)<1e-12)e->excitation.firing=command;
}
