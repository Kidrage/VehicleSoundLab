#include "modules.h"
#include "engine.h"
#include "profiles/voicing.h"
#include <math.h>
static double follow(double now,double target,double seconds,double dt) {
    return now+(1-exp(-dt/seconds))*(target-now);
}
/* Independent response envelopes; state labels now select explicit tone maps.
   Shift attenuation is kept separate from lifecycle combustion, so a torque
   cut need not erase the body/structure at the same speed as intake detail. */
void vsl_orchestrate(VslEngine *e,double dt) {
    VslVoicing *v=&e->voice;VslDrive *d=&e->drive;
    const VslVoicingProfile *p=vsl_voicing_profile(e->target.profile);
    double level[VSL_LAYERS]={0},base[VSL_LAYERS],tilt=0,cutoff=0;
    double *gain[VSL_LAYERS]={&v->dna_gain,&v->body_gain,&v->intake_gain,
        &v->mechanical_gain,&v->air_gain,&v->high_gain};
    double idle=1-vsl_clamp((d->rpm-vsl_profile(e->target.profile)->idle_rpm)/1500,0,1);
    double pull=fmax(0,d->load),over=fmax(0,-d->load),catching=0;
    int i,j,op=d->operating;
    if(op<0||op>=VSL_OPERATING_COUNT)op=VSL_IDLE;
    if(d->lifecycle==VSL_CATCH)catching=d->lifecycle_flare;
    if(d->lifecycle!=VSL_RUNNING)op=VSL_IDLE;
    v->combustion=follow(v->combustion,d->combustion,.020,dt);
    v->idle=follow(v->idle,idle,.035,dt);
    v->pull=follow(v->pull,pull,.035,dt);v->overrun=follow(v->overrun,over,.035,dt);
    /* Neutral and RPM/load bench have no longitudinal-acceleration colour. */
    v->accel=follow(v->accel,d->gear&&e->target.drive_mode!=VSL_BENCH?fmax(0,d->acceleration):0,.060,dt);
    v->decel=follow(v->decel,d->gear&&e->target.drive_mode!=VSL_BENCH?fmax(0,-d->acceleration):0,.080,dt);
    v->catch_weight=follow(v->catch_weight,catching,.012,dt);
    for(i=0;i<VSL_OPERATING_COUNT;++i) {
        v->state_mix[i]=follow(v->state_mix[i],i==op?1:0,.035,dt);
        for(j=0;j<VSL_LAYERS;++j)level[j]+=v->state_mix[i]*p->state[i].level[j];
        tilt+=v->state_mix[i]*p->state[i].tilt_delta;
        cutoff+=v->state_mix[i]*p->state[i].cutoff_ratio;
    }
    v->tilt_delta=follow(v->tilt_delta,tilt+.025*over*v->decel-.06*v->catch_weight,.025,dt);
    v->cutoff_ratio=follow(v->cutoff_ratio,fmax(.4,cutoff)*(1+.22*v->catch_weight),.025,dt);
    v->release_mass=follow(v->release_mass,pull,pull>v->release_mass?.045:e->smooth.release_time,dt);
    base[VSL_LAYER_EXHAUST]=(.30+.64*pull)*(1-.38*over)*(1+.07*v->accel+.12*over*v->decel);
    base[VSL_LAYER_BODY]=.28+.45*idle*e->smooth.idle_body+.30*v->release_mass+.20*over;
    base[VSL_LAYER_INTAKE]=.025+.16*d->engine_throttle+.12*pull+.055*v->accel;
    base[VSL_LAYER_MECHANICAL]=.035+.05*idle+.025*pull;
    base[VSL_LAYER_AIR]=.01+.12*pull+.035*over*(1+.6*v->decel);
    base[VSL_LAYER_HIGH]=(.08+.92*pull)*(1+.12*v->accel);
    for(i=0;i<VSL_LAYERS;++i) {
        double cut=vsl_clamp(1-p->cut_depth[i]*(1-d->shift_gain),0,1),target;
        /* Brief combustion/airflow from a rev match can rise while torque is
           disconnected. Body and mechanics retain their slower response. */
        cut=fmax(cut,p->rev_match_relief[i]*vsl_clamp(d->blip/.35,0,1));
        double seconds=cut<v->cut[i]?p->cut_seconds[i]:p->recover_seconds[i];
        v->cut[i]=follow(v->cut[i],cut,seconds,dt);
        target=d->combustion*base[i]*level[i]*v->cut[i]*(1+v->catch_weight*(p->catch_level[i]-1));
        seconds=target>*gain[i]?p->attack[i]:p->release[i];
        *gain[i]=follow(*gain[i],target,seconds,dt);
    }
    {
        double rotation=vsl_clamp((d->rpm-40)/fmax(1,vsl_profile(e->target.profile)->idle_rpm-40),0,1);
        double target;
        if(d->lifecycle==VSL_OFF||d->lifecycle==VSL_READY)rotation=0;
        target=rotation*base[VSL_LAYER_MECHANICAL]*level[VSL_LAYER_MECHANICAL]*v->cut[VSL_LAYER_MECHANICAL];
        v->mechanical_motion_gain=follow(v->mechanical_motion_gain,target,.025,dt);
    }
}
