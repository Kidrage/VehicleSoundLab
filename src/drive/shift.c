#include "shift.h"
#include "powertrain.h"
#include "profiles/transmission.h"
#include "profiles/clutch.h"
#include "core/modules.h"
#include <math.h>
static double ease(double x) { x=vsl_clamp(x,0,1);return x*x*(3-2*x); }
const char *vsl_shift_stage_name(VslShiftStage stage) {
    static const char *names[]={"NONE","DISCONNECT","MATCH","ENGAGE"};
    return names[stage>=VSL_SHIFT_NONE&&stage<=VSL_SHIFT_ENGAGE?stage:0];
}
void vsl_shift_cancel(VslDrive *d) {
    d->shifting=0;d->shift_stage=VSL_SHIFT_NONE;d->stage_seconds=0;
    d->shift_gain=1;d->clutch_transfer=1;d->blip=0;d->shift_error=0;
}
int vsl_shift_request(VslDrive *d,int next,double max_rpm) {
    if(next<0 || next>7 || next==d->gear || d->shifting || d->shift_lock>0 ||
       d->lifecycle!=VSL_RUNNING || (next && d->speed_kph*vsl_gear_ratio(next)>=max_rpm*.98))return 0;
    d->previous_gear=d->gear;d->requested_gear=next;d->gear=next;d->shifting=1;
    d->shift_direction=!next||!d->previous_gear?0:(next>d->previous_gear?1:-1);
    d->shift_stage=VSL_SHIFT_DISCONNECT;d->stage_seconds=d->shift_seconds=0;
    d->shift_from_rpm=d->rpm;d->blip=0;++d->shift_events;
    return 1;
}
static void abort_shift(VslDrive *d,const VslTransmissionProfile *p) {
    /* A failed match opens the driveline instead of forcing engagement. */
    vsl_shift_cancel(d);d->gear=d->requested_gear=0;d->shift_lock=p->cooldown;
    ++d->aborted_shifts;
}
void vsl_shift_step(VslDrive *d,double idle,double maxrpm,double dt) {
    const VslTransmissionProfile *p=vsl_transmission_profile(d->profile);
    double coupled=d->speed_kph*vsl_gear_ratio(d->gear),target,old_target=d->shift_target_rpm;
    d->blip=0;
    if(!d->shifting)return;
    d->shift_seconds+=dt;d->stage_seconds+=dt;
    if(d->shift_seconds>p->disconnect+p->timeout+p->engage+.05) { abort_shift(d,p);return; }
    target=d->gear?fmax(idle,coupled):idle+d->throttle*(maxrpm-idle);
    /* At launch the clutch remains partially slipping, like the normal drive
       controller; this prevents a spurious jump back to idle after the shift. */
    if(d->gear) {
        double coupling=ease((d->speed_kph-4)/20);
        target=(idle+d->throttle*(2600-idle))*(1-coupling)+target*coupling;
    }
    d->shift_target_rpm=vsl_clamp(target,idle,maxrpm);
    d->shift_target_rate=vsl_clamp((d->shift_target_rpm-old_target)/dt,-p->max_fall,p->max_rise);
    if(d->gear && coupled>=maxrpm*.98) { abort_shift(d,p);return; }
    if(d->shift_stage==VSL_SHIFT_DISCONNECT) {
        double x=ease(d->stage_seconds/p->disconnect);
        d->clutch_transfer=1-x;d->shift_gain=1-(1-p->cut_floor)*x;
        d->operating=VSL_SHIFT_CUT;
        if(d->stage_seconds>=p->disconnect) { d->shift_stage=VSL_SHIFT_MATCH;d->stage_seconds=0; }
    } else {
        if(d->shift_stage==VSL_SHIFT_MATCH) {
            double minimum=d->shift_direction<0?p->down_match_min:p->up_match_min;
            /* An upshift can dissipate/transfer engine kinetic energy through
               the incoming clutch. Downshift and neutral matching stay open. */
            const VslClutchProfile *clutch=vsl_clutch_profile(d->profile);
            d->clutch_transfer=d->shift_direction>0?clutch->upshift_sync_capacity_nm/clutch->capacity_nm:0;
            d->shift_gain=p->cut_floor;
            d->operating=VSL_SHIFT_CUT;
            if(d->stage_seconds>=minimum && (!d->gear||fabs(d->shift_target_rpm-d->rpm)<=p->tolerance)) {
                d->shift_stage=VSL_SHIFT_ENGAGE;d->stage_seconds=0;d->blip=0;
            } else if(d->stage_seconds>=p->timeout) { abort_shift(d,p);return; }
        } else {
            /* A changed road target must be rematched before torque returns. */
            if(d->gear&&fabs(d->shift_target_rpm-d->rpm)>p->engage_tolerance) {
                d->shift_stage=VSL_SHIFT_MATCH;d->stage_seconds=0;d->clutch_transfer=0;
                d->shift_gain=p->cut_floor;d->operating=VSL_SHIFT_CUT;
            } else {
                double x=ease(d->stage_seconds/p->engage);
                const VslClutchProfile *clutch=vsl_clutch_profile(d->profile);
                double initial=d->shift_direction>0?clutch->upshift_sync_capacity_nm/clutch->capacity_nm:0;
                d->clutch_transfer=initial+(1-initial)*x;
                d->shift_gain=p->cut_floor+(1-p->cut_floor)*x;
                d->operating=VSL_SHIFT_RECOVER;
                if(d->stage_seconds>=p->engage) { vsl_shift_cancel(d);d->shift_lock=p->cooldown; }
            }
        }
    }
    d->shift_error=d->shift_target_rpm-d->rpm;
}
