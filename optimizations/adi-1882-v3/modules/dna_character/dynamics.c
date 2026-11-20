#include "dynamics.h"
#include "core/modules.h"
#include <math.h>
void dch_dynamics_targets(const VslEngine *e,float *line,float *air) {
    const VslDrive *d=&e->drive;const VslVoicing *v=&e->voice;
    float coast,rotation,shift,line_floor,air_floor;
    *line=*air=v->dna_gain;
    /* Startup, accepted idle/power and the legacy adapters keep their exact
       envelopes. Coasting is not a command to turn the rotating engine off. */
    if(d->lifecycle!=VSL_RUNNING)return;
    rotation=vsl_clamp((d->rpm-vsl_profile(e->target.profile)->idle_rpm-300)/600,0,1);
    coast=v->state_mix[VSL_OVERRUN];
    if(d->throttle<.14f&&d->load<=.03f)
        coast+=v->state_mix[VSL_SHIFT_CUT]+v->state_mix[VSL_SHIFT_RECOVER]+v->state_mix[VSL_REV_MATCH];
    coast=vsl_clamp(coast,0,1)*rotation;
    shift=vsl_clamp(d->shift_gain,0,1);
    /* Provisional sound-design floors, before user state multipliers. They
       retain less line through torque cuts, but more rotating/air texture.
       Combustion/lifecycle permission still owns shutdown. */
    line_floor=.50f*(.40f+.60f*shift)*d->combustion*coast;
    air_floor=.64f*(.75f+.25f*shift)*d->combustion*coast;
    *line=fmaxf(*line,line_floor);*air=fmaxf(*air,air_floor);
}
