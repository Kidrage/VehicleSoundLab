#include "drive.h"
#include "powertrain.h"
#include "shift.h"
#include "fueling.h"
#include "lifecycle.h"
#include "longitudinal.h"
#include "core/engine.h"
#include "core/modules.h"
#include <math.h>
#include <string.h>
/* Independently implemented C controller. V6 reference: fixed control clock,
   start latch, integrated speed, coupled RPM, cut/sweep/recovery and armed lift.
   These constants are engineering settings, not measured Lamborghini telemetry. */
static double ease(double x) { x=vsl_clamp(x,0,1);return x*x*(3-2*x); }
static double follow(double x,double to,double seconds,double dt) { return x+(to-x)*(1-exp(-dt/seconds)); }
const char *vsl_operating_name(VslOperating s) {
    static const char *n[]={"IDLE","FREE REV","PULL","CRUISE","OVERRUN","SHIFT CUT","SHIFT RECOVER","REV MATCH"};
    return n[s>=VSL_IDLE&&s<VSL_OPERATING_COUNT?s:0];
}
void vsl_drive_reset(VslDrive *d,int profile) {
    memset(d,0,sizeof *d); d->profile=profile;d->gear=d->requested_gear=1;
    vsl_shift_cancel(d);d->release_seconds=-1;
}
void vsl_drive_step(VslDrive *d,const VslParams *p,double dt) {
    const VslProfile *profile=vsl_profile(p->profile);
    double idle=profile->idle_rpm,maxrpm=profile->max_rpm;
    double pedal=p->throttle,brake=p->brake,old=d->throttle,target;
    double old_engine_throttle=d->engine_throttle;
    int old_start=d->last_start;VslOperating old_operating=d->operating;
    dt=vsl_clamp(dt,.001,.05);
    d->overrun_strength=0;
    d->shift_lock=fmax(0,d->shift_lock-dt);d->cooldown=fmax(0,d->cooldown-dt);
    if(d->profile!=p->profile) {
        /* Profile changes require a fresh start, avoiding inherited voice state. */
        int was_active=d->lifecycle!=VSL_OFF;
        vsl_drive_reset(d,p->profile);
        d->last_start=old_start;
        if(was_active) { d->last_start=p->start_id;return; }
    }
    if(!vsl_lifecycle_step(d,p,dt)) {
        d->throttle=d->load=d->acceleration=0;
        d->engine_throttle=d->engine_throttle_rate=d->throttle_rate=d->blip=0;
        if(p->drive_mode!=VSL_BENCH) {
            d->brake=follow(d->brake,p->brake,.04,dt);
            vsl_longitudinal_step(d,idle,maxrpm,dt);
        } else { d->brake=0;memset(&d->vehicle,0,sizeof d->vehicle); }
        d->operating=VSL_IDLE;
        vsl_fueling_step(d,p,dt);
        return;
    }
    d->running_seconds+=dt;d->combustion=1;
    if(p->drive_mode==VSL_AUTODRIVE) {
        /* A repeatable pedal scenario, never a prescribed RPM trajectory. */
        double t=fmod(d->running_seconds,30.0);
        if(t<1.5) { pedal=0;brake=0; }
        else if(t<4) { pedal=.20+.74*ease((t-1.5)/2.5);brake=0; }
        else if(t<14) { pedal=.94;brake=0; }
        else if(t<17) { pedal=0;brake=0; }
        else if(t<20) { pedal=.55;brake=0; }
        else { pedal=0;brake=.78; }
    }
    if(p->drive_mode==VSL_BENCH)pedal=fmax(0,p->load);
    d->throttle=follow(d->throttle,pedal,pedal>old?.025:.035,dt);
    d->brake=follow(d->brake,brake,.04,dt);
    d->throttle_rate=(d->throttle-old)/dt;
    if(!d->shifting && d->shift_lock<=0 && p->drive_mode!=VSL_BENCH) {
        int next=p->gear;
        if(p->auto_gear || p->drive_mode==VSL_AUTODRIVE) {
            next=d->gear?d->gear:(d->throttle>.18?1:0);
            /* Sport policy selected by the user: lift holds the gear. A falling
               pedal must not lower an upshift threshold and invent extra cuts.
               Braking requests useful engine speed, with a hard overspeed guard. */
            int powering=d->throttle>.18 && d->throttle_rate>=-.35 && d->brake<.10;
            int braking=d->brake>.12 && d->rpm<4200+1800*d->brake;
            int low_powered=d->throttle>.16 && d->throttle_rate>=-.35 && d->rpm<1800+1000*d->throttle;
            if(powering && d->rpm>maxrpm*(.84+.13*d->throttle) && next<7)++next;
            else if(next>1 && (braking||low_powered) && d->speed_kph*vsl_gear_ratio(next-1)<maxrpm*.90)--next;
        }
        (void)vsl_shift_request(d,next,maxrpm);
    }
    d->previous_rpm=d->rpm;
    if(p->drive_mode==VSL_BENCH && d->shifting)vsl_shift_cancel(d);
    if(d->shifting)vsl_shift_step(d,idle,maxrpm,dt);
    else { d->shift_gain=d->clutch_transfer=1;d->blip=0; }
    if(p->drive_mode!=VSL_BENCH)vsl_longitudinal_step(d,idle,maxrpm,dt);
    else memset(&d->vehicle,0,sizeof d->vehicle);
    if(p->drive_mode==VSL_BENCH) {
        target=p->rpm;
        d->rpm=follow(d->rpm,vsl_clamp(target,idle,10000),target>d->rpm?.10:.17,dt);
    }
    if(p->drive_mode==VSL_BENCH)d->engine_throttle=d->throttle;
    d->engine_throttle_rate=(d->engine_throttle-old_engine_throttle)/dt;
    d->rpm_rate=(d->rpm-d->previous_rpm)/dt;
    /* Actual applied net torque, including explicit idle/launch/sync control.
       Clutch friction, not an RPM follower, drives the wheel-side reaction. */
    d->load=p->drive_mode==VSL_BENCH?p->load:vsl_clamp(
        d->vehicle.shaft_torque_nm/d->vehicle.available_torque_nm,-1,1);
    if(p->drive_mode!=VSL_BENCH && d->rpm<idle+150 && d->throttle<.06)d->load=.04;
    if(!d->shifting) {
        if(p->drive_mode==VSL_BENCH) {
            /* A positive bench load is not a released pedal, even while the
               synthetic throttle follower is still catching up. */
            d->acceleration=0;
            if(d->rpm<idle+180)d->operating=VSL_IDLE;
            else d->operating=d->load<-.03?VSL_OVERRUN:VSL_FREE_REV;
        } else {
            double idle_limit=old_operating==VSL_IDLE?230:180;
            double lift_limit=old_operating==VSL_OVERRUN?.14:.10;
            double pull_pedal=old_operating==VSL_PULL?.28:.35;
            double pull_accel=old_operating==VSL_PULL?.04:.08;
            if(d->rpm<idle+idle_limit && d->throttle<.06)d->operating=VSL_IDLE;
            else if(d->throttle<lift_limit && d->load<-.03 && d->rpm>idle+300)d->operating=VSL_OVERRUN;
            else if(d->gear==0)d->operating=VSL_FREE_REV;
            else if(d->throttle>pull_pedal && d->acceleration>pull_accel)d->operating=VSL_PULL;
            else d->operating=VSL_CRUISE;
        }
    }
    vsl_fueling_step(d,p,dt);
    /* A loud high-RPM history must arm a short release window. Low RPM,
       brake-only motion, a slow release and ignition-off cannot fire pops. */
    if(!d->overrun_armed) {
        if(d->throttle>.35 && d->rpm>1600) {
            d->armed_seconds+=dt;d->peak_throttle=fmax(d->peak_throttle,d->throttle);
            if(d->armed_seconds>=.12)d->overrun_armed=1;
        } else { d->armed_seconds=0;d->peak_throttle=0; }
    } else {
        d->peak_throttle=fmax(d->peak_throttle,d->throttle);
        if(d->release_seconds<0 && d->throttle_rate<-.5)d->release_seconds=0;
        if(d->release_seconds>=0) {
            d->release_seconds+=dt;
            if(d->throttle<.18 && d->peak_throttle-d->throttle>.35 && d->release_seconds<.24 && d->cooldown==0 && d->rpm>1600 && !d->shifting) {
                d->overrun_strength=vsl_clamp(.35+.4*d->peak_throttle+.25*(d->rpm-1600)/5000,0,1);
                if(p->backfire)++d->overrun_events;
                d->cooldown=.35;d->overrun_armed=0;d->armed_seconds=0;d->release_seconds=-1;d->peak_throttle=0;
            } else if(d->release_seconds>.24) {
                d->overrun_armed=0;d->armed_seconds=0;d->release_seconds=-1;d->peak_throttle=0;
            }
        }
    }
}
