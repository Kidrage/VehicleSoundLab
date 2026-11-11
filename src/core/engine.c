#include "engine.h"
#include "modules.h"
#include "character.h"
#include "event_color.h"
#include "firing_source.h"
#include "drive/drive.h"
#include "spatial/scene.h"
#include "spatial/propagation.h"
#include <math.h>
#include <string.h>
double vsl_clamp(double v,double lo,double hi) { return !isfinite(v)?lo:(v<lo?lo:(v>hi?hi:v)); }
void vsl_init(VslEngine *e,double sr,uint32_t seed) {
    static const unsigned taps[]={0,313,709,1153,1877,2683};
    static const float gain[]={.65f,.12f,-.08f,.06f,.04f,-.025f};unsigned i;
    memset(e,0,sizeof *e);e->sample_rate=vsl_clamp(sr,16000,192000);
    e->target=e->smooth=vsl_default_params(0);e->control_period=(unsigned)(e->sample_rate/200+.5);
    e->nvh.seed=seed?seed:48271;e->events.seed=e->nvh.seed^0x9e3779b9u;
    e->mechanical.rotating_seed=e->nvh.seed^0x6d2b79f5u;
    e->mechanical.fired_seed=e->nvh.seed^0xa511e9b3u;
    if(!e->mechanical.rotating_seed)e->mechanical.rotating_seed=1;
    if(!e->mechanical.fired_seed)e->mechanical.fired_seed=1;
    vsl_combustion_init(e,e->nvh.seed);
    vsl_character_init(e,e->nvh.seed);
    vsl_firing_source_init(&e->firing_source,e->sample_rate);
    vsl_drive_reset(&e->drive,0);
    vsl_excitation_init(e);
    vsl_propagation_init(&e->spatial.propagation);
    e->acoustics.tap_count=6;
    for(i=0;i<6;++i) {
        unsigned t=(unsigned)(taps[i]*e->sample_rate/48000);
        if(t>=VSL_MAX_IR)t=VSL_MAX_IR-1;
        e->acoustics.taps[i]=t;e->acoustics.ir[t]=gain[i];e->acoustics.ir_length=t+1;
    }
}
void vsl_set_params(VslEngine *e,const VslParams *p) {
    e->target=*p;
    if(p->profile<0||p->profile>=VSL_PROFILE_COUNT)e->target.profile=0;
    e->target.rpm=vsl_clamp(p->rpm,0,10000);e->target.load=vsl_clamp(p->load,-1,1);
#define UNIT(f) e->target.f=vsl_clamp(p->f,0,1)
    UNIT(master);UNIT(dna);UNIT(pad);UNIT(noise);UNIT(brightness);UNIT(space);
    UNIT(throttle);UNIT(brake);UNIT(width);UNIT(perspective);UNIT(detail);UNIT(intake);UNIT(mechanical);
    UNIT(idle_body);UNIT(irregularity);UNIT(event_level);
    UNIT(pumping);
    UNIT(pressure_texture);UNIT(structure_transfer);UNIT(response_shape);UNIT(event_color);UNIT(pulse_amount);
#undef UNIT
    e->target.release_time=vsl_clamp(p->release_time,.08,1.2);
    e->target.drive_mode=(int)vsl_clamp(p->drive_mode,VSL_BENCH,VSL_AUTODRIVE);
    e->target.gear=(int)vsl_clamp(p->gear,0,7);
    e->target.ignition=p->ignition?1:0;e->target.backfire=p->backfire?1:0;
    e->target.auto_gear=p->auto_gear?1:0;e->target.pure_osc=p->pure_osc?1:0;
    e->target.fuel_cut=p->fuel_cut?1:0;
    e->target.mechanical_model=p->mechanical_model?1:0;
    e->target.combustion_variation=p->combustion_variation?1:0;
    e->target.propagation=p->propagation?1:0;
    e->target.firing_source=(int)vsl_clamp(p->firing_source,VSL_SOURCE_OSC,VSL_SOURCE_VARIABLE);
}
int vsl_process_layout(VslEngine *e,float *out,unsigned frames,int channels,float *stems) {
    unsigned i;int c;double fast=1-exp(-1/(.018*e->sample_rate));
    if(channels!=2&&channels!=12)return 0;
    for(i=0;i<frames;++i) {
        double l,r,bed,event,spatial[VSL_MAX_CHANNELS],ir,main_pressure[2];
        VslObjectFrame *o=&e->objects;memset(o,0,sizeof *o);
        if(e->frame%e->control_period==0) {
            vsl_drive_step(&e->drive,&e->target,e->control_period/e->sample_rate);
            vsl_orchestrate(e,e->control_period/e->sample_rate);vsl_events_update(e);
            vsl_scene_update(e,channels);
        }
        e->smooth.profile=e->target.profile;e->smooth.pure_osc=e->target.pure_osc;
        e->control.rpm+=fast*(e->drive.rpm-e->control.rpm);
        e->control.load+=fast*(e->drive.load-e->control.load);
        e->control.throttle=e->drive.engine_throttle;e->control.throttle_delta=e->drive.engine_throttle_rate;
        e->control.acceleration=e->drive.acceleration;
#define FOLLOW(f) e->smooth.f+=fast*(e->target.f-e->smooth.f)
        FOLLOW(master);FOLLOW(dna);FOLLOW(pad);FOLLOW(noise);FOLLOW(brightness);
        FOLLOW(width);FOLLOW(perspective);FOLLOW(detail);FOLLOW(intake);FOLLOW(mechanical);
        FOLLOW(idle_body);FOLLOW(irregularity);FOLLOW(release_time);FOLLOW(event_level);
        FOLLOW(pumping);
        FOLLOW(pressure_texture);FOLLOW(structure_transfer);FOLLOW(response_shape);FOLLOW(event_color);FOLLOW(pulse_amount);
#undef FOLLOW
        e->smooth.space+=fast*((e->target.pure_osc?0:e->target.space)-e->smooth.space);
        vsl_clocks_tick(e);
        vsl_combustion_tick(e);
        if(e->frame%128==0) { vsl_dna_update(e);vsl_high_orders_update(e); }
        vsl_dna_tick(e,&l,&r);o->sample[VSL_EXHAUST_L]=l*e->smooth.dna*.65;
        o->sample[VSL_EXHAUST_R]=r*e->smooth.dna*.65;
        vsl_high_orders_tick(e,o);main_pressure[0]=o->sample[0];main_pressure[1]=o->sample[1];vsl_excitation_tick(e,o);vsl_mechanical_tick(e,o);
        bed=vsl_pad_tick(e)*e->smooth.pad;event=vsl_events_tick(e);
        vsl_nvh_tick(e,o);o->sample[VSL_BODY]=bed;
        o->sample[VSL_EVENT]=event*e->smooth.noise*e->smooth.event_level*2;
        e->fade+=fast*((e->target.pure_osc?0:1)-e->fade);
        for(c=VSL_INTAKE;c<VSL_OBJECTS;++c)o->sample[c]*=e->fade;
        vsl_character_tick(e,o);
        e->color.amount=e->smooth.event_color;vsl_color_tick(&e->color,e,o,main_pressure);
        vsl_firing_source_tick(&e->firing_source,e,o,main_pressure);
        ir=vsl_ir_tick(e,.5*(o->sample[0]+o->sample[1]));
        o->sample[VSL_BODY]+=(ir-.5*(o->sample[0]+o->sample[1]))*e->fade*.25;
        if(stems)for(c=0;c<VSL_OBJECTS;++c)stems[i*VSL_OBJECTS+c]=(float)o->sample[c];
        vsl_scene_tick(e,o,spatial,channels);++e->frame;
        for(c=0;c<channels;++c) {
            double x=spatial[c]*e->smooth.master;
            out[i*channels+c]=(float)vsl_clamp(x,-.95,.95);
            e->peak=fmax(fabs(out[i*channels+c]),e->peak*.99998);
        }
    }
    return 1;
}
void vsl_process(VslEngine *e,float *out,unsigned frames) { (void)vsl_process_layout(e,out,frames,2,NULL); }
void vsl_drive(double t,VslParams *p) {
    /* Old host API: time is integrated only inside drive.c. */
    (void)t;p->drive_mode=VSL_AUTODRIVE;p->ignition=1;if(!p->start_id)p->start_id=1;
}
