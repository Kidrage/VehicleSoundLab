#include "motion.h"
#include "core/modules.h"
#include "drive/fueling.h"
#include "profiles/fueling.h"
#include <math.h>
#if defined(VSL_DSP_STATIC) && defined(VSL_DSP_APPROX)
/* Parameters and rate are immutable between control edits. Preserve the
   original FP32 expression, including its multiplication order. */
static const VslFuelingProfile *motion_cached_profile;
static float motion_cached_rate,motion_attack,motion_release;
#endif

void da_motion_tick(VslEngine *e,float follow) {
    const VslFuelingProfile *p=vsl_fueling_profile(e->target.profile);
    float command=vsl_fueling_allows_firing(&e->drive)?1.f:0.f;
    float coefficient;
#if defined(VSL_DSP_STATIC) && defined(VSL_DSP_APPROX)
    if(p!=motion_cached_profile||e->sample_rate!=motion_cached_rate){
        motion_attack=1-expf(-1/(p->attack_seconds*e->sample_rate));
        motion_release=1-expf(-1/(p->release_seconds*e->sample_rate));
        motion_cached_profile=p;motion_cached_rate=e->sample_rate;
    }
    coefficient=command>e->excitation.firing?motion_attack:motion_release;
#else
    float seconds=command>e->excitation.firing?p->attack_seconds:p->release_seconds;
    coefficient=1-expf(-1/(seconds*e->sample_rate));
#endif
    e->control.rpm+=follow*(e->drive.rpm-e->control.rpm);
    e->control.load+=follow*(e->drive.load-e->control.load);
    e->control.throttle=e->drive.engine_throttle;
    e->control.throttle_delta=e->drive.engine_throttle_rate;
    e->control.acceleration=e->drive.acceleration;
    /* Physical720-degree cycle; never retime the independent acoustic atlas. */
    vsl_clocks_tick(e);
    /* Mechanical resonators read this envelope plus strict firing permission.
       No call to excitation_tick: it would alter the atlas exhaust signal. */
    e->excitation.firing+=coefficient*(command-e->excitation.firing);
    if(fabsf(e->excitation.firing-command)<1e-12f)e->excitation.firing=command;
}
