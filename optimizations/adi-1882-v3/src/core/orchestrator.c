#include "dsp/perf.h"
#include "modules.h"
#include "engine.h"
#include "profiles/voicing.h"
#include <math.h>
static float follow(float now,float target,float seconds,float dt) {
    return now+(1-expf(-dt/seconds))*(target-now);
}
/* Independent response envelopes; state labels now select explicit tone maps.
   Shift attenuation is kept separate from lifecycle combustion, so a torque
   cut need not erase the body/structure at the same speed as intake detail. */
void vsl_orchestrate(VslEngine *e,float dt);
void vsl_orchestrate_impl(VslEngine *e,float dt){
    VslVoicing *v=&e->voice;VslDrive *d=&e->drive;
    const VslVoicingProfile *p=vsl_voicing_profile(e->target.profile);
    float level[VSL_LAYERS]={0},base[VSL_LAYERS],tilt=0,cutoff=0;
    float *gain[VSL_LAYERS]={&v->dna_gain,&v->body_gain,&v->intake_gain,
        &v->mechanical_gain,&v->air_gain,&v->high_gain};
    float idle=1-vsl_clamp((d->rpm-vsl_profile(e->target.profile)->idle_rpm)/1500,0,1);
    float pull=fmaxf(0,d->load),over=fmaxf(0,-d->load),catching=0;
    int i,j,op=d->operating;
    if(op<0||op>=VSL_OPERATING_COUNT)op=VSL_IDLE;
    if(d->lifecycle==VSL_CATCH)catching=d->lifecycle_flare;
    if(d->lifecycle!=VSL_RUNNING)op=VSL_IDLE;
    v->combustion=follow(v->combustion,d->combustion,.020f,dt);
    v->idle=follow(v->idle,idle,.035f,dt);
    v->pull=follow(v->pull,pull,.035f,dt);v->overrun=follow(v->overrun,over,.035f,dt);
    /* Neutral and RPM/load bench have no longitudinal-acceleration colour. */
    v->accel=follow(v->accel,d->gear&&e->target.drive_mode!=VSL_BENCH?fmaxf(0,d->acceleration):0,.060f,dt);
    v->decel=follow(v->decel,d->gear&&e->target.drive_mode!=VSL_BENCH?fmaxf(0,-d->acceleration):0,.080f,dt);
    v->catch_weight=follow(v->catch_weight,catching,.012f,dt);
    for(i=0;i<VSL_OPERATING_COUNT;++i) {
        v->state_mix[i]=follow(v->state_mix[i],i==op?1.f:0.f,.035f,dt);
        for(j=0;j<VSL_LAYERS;++j)level[j]+=v->state_mix[i]*p->state[i].level[j];
        tilt+=v->state_mix[i]*p->state[i].tilt_delta;
        cutoff+=v->state_mix[i]*p->state[i].cutoff_ratio;
    }
    v->tilt_delta=follow(v->tilt_delta,tilt+.025f*over*v->decel-.06f*v->catch_weight,.025f,dt);
    v->cutoff_ratio=follow(v->cutoff_ratio,fmaxf(.4f,cutoff)*(1+.22f*v->catch_weight),.025f,dt);
    v->release_mass=follow(v->release_mass,pull,pull>v->release_mass?.045f:e->smooth.release_time,dt);
    base[VSL_LAYER_EXHAUST]=(.30f+.64f*pull)*(1-.38f*over)*(1+.07f*v->accel+.12f*over*v->decel);
    base[VSL_LAYER_BODY]=.28f+.45f*idle*e->smooth.idle_body+.30f*v->release_mass+.20f*over;
    base[VSL_LAYER_INTAKE]=.025f+.16f*d->engine_throttle+.12f*pull+.055f*v->accel;
    base[VSL_LAYER_MECHANICAL]=.035f+.05f*idle+.025f*pull;
    base[VSL_LAYER_AIR]=.01f+.12f*pull+.035f*over*(1+.6f*v->decel);
    base[VSL_LAYER_HIGH]=(.08f+.92f*pull)*(1+.12f*v->accel);
    for(i=0;i<VSL_LAYERS;++i) {
        float cut=vsl_clamp(1-p->cut_depth[i]*(1-d->shift_gain),0,1),target;
        /* Brief combustion/airflow from a rev match can rise while torque is
           disconnected. Body and mechanics retain their slower response. */
        cut=fmaxf(cut,p->rev_match_relief[i]*vsl_clamp(d->blip/.35f,0,1));
        float seconds=cut<v->cut[i]?p->cut_seconds[i]:p->recover_seconds[i];
        v->cut[i]=follow(v->cut[i],cut,seconds,dt);
        target=d->combustion*base[i]*level[i]*v->cut[i]*(1+v->catch_weight*(p->catch_level[i]-1));
        seconds=target>*gain[i]?p->attack[i]:p->release[i];
        *gain[i]=follow(*gain[i],target,seconds,dt);
    }
    {
        float rotation=vsl_clamp((d->rpm-40)/fmaxf(1,vsl_profile(e->target.profile)->idle_rpm-40),0,1);
        float target;
        if(d->lifecycle==VSL_OFF||d->lifecycle==VSL_READY)rotation=0;
        target=rotation*base[VSL_LAYER_MECHANICAL]*level[VSL_LAYER_MECHANICAL]*v->cut[VSL_LAYER_MECHANICAL];
        v->mechanical_motion_gain=follow(v->mechanical_motion_gain,target,.025f,dt);
    }
}
void vsl_orchestrate(VslEngine *e,float dt){vsl_perf_enter(10);vsl_orchestrate_impl(e,dt);vsl_perf_leave();}

