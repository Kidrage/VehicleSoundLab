#include "render.h"
#include "core/engine.h"
#include "core/modules.h"
#include "drive/drive.h"
#include "spatial/scene.h"
#include "rt_numeric/scope.h"
#include "profiles/lifecycle.h"
#include <math.h>
#include <string.h>
static void amounts(const AdControl *p,double a[DA_LAYERS]) {
    a[DA_INTAKE]=p->mix.intake_gain;a[DA_MECHANICAL]=p->mix.mechanical_gain;
    a[DA_AIR]=p->mix.air_gain;a[DA_ROAD]=p->mix.road_gain;a[DA_WIND]=p->mix.wind_gain;
}

int ad_render_init(AdRender *s,VslEngine *e,const AdConfig *c,const AdControl *p) {
    unsigned a;double aux[DA_LAYERS];
    if (!s||!e||!c||!c->bank||!c->bank->count||c->bank->count>SA_MAX_ANCHORS||!ad_control_valid(p,c->channels)||
        c->profile<0||c->profile>=VSL_PROFILE_COUNT||!isfinite(c->root_per_rpm)||
        c->root_per_rpm<=0||c->root_per_rpm>.1||!ds_routing_valid(c->projection,c->route)||
        (!c->residual_bank&&p->mix.residual_gain>0)||(!c->startup_profile&&p->mix.startup_gain>0)||(!c->catch_profile&&p->mix.catch_gain>0)||
        (!c->resonant_bank&&p->mix.resonant_gain>0)||
        (!c->recipe_bank&&p->mix.coherent_low_gain>0)||
        (c->scene_mode!=AD_SCENE_OBJECTS&&c->scene_mode!=AD_SCENE_STEREO_BED)) return 0;
    if(c->residual_bank) {
        if(!ra_bank_valid(c->residual_bank)||c->residual_bank->count!=c->bank->count)return 0;
        for(a=0;a<c->bank->count;++a)if(!c->bank->profile[a]||fabs(c->residual_bank->root[a]-c->bank->profile[a]->base_hz)>1e-8)return 0;
    }
    if(c->startup_profile&&!st_profile_valid(c->startup_profile))return 0;
    if(c->catch_profile&&!cb_profile_valid(c->catch_profile))return 0;
    if(c->resonant_bank&&!drs_bank_valid(c->resonant_bank,c->bank))return 0;
    if(c->recipe_bank&&!drc_bank_valid(c->recipe_bank,c->bank,c->resonant_bank))return 0;
    memset(s,0,sizeof *s);
    if(!sb_layout_init(&s->bed_layout,(unsigned)c->channels))return 0;
    if(c->startup_profile&&!st_voice_init(&s->startup,c->startup_profile,c->seed^UINT64_C(0xf4c25171),p->mix.startup_gain))return 0;
    if(c->catch_profile&&!cb_voice_init(&s->catch_bloom,c->catch_profile,p->mix.catch_gain))return 0;
    if (!sa_voice_init(&s->dna,c->bank,c->seed,0,p->mix.detail,1)) return 0;
    if(c->resonant_bank&&!drs_voice_init(&s->resonant,c->resonant_bank,c->bank,c->seed^UINT64_C(48271)^UINT64_C(8121907),p->mix.resonant_gain))return 0;
    if(c->recipe_bank&&!drc_voice_init(&s->recipe,c->recipe_bank,c->bank,c->resonant_bank,c->seed,p->mix.coherent_low_gain))return 0;
    s->body_band=hb_band_default();
    /* Engineering voicing scale, not a measured structural transfer. */
    if(!hb_mix_init(&s->body,48000,p->mix.body_mix,1.6))return 0;
    if(c->residual_bank&&!ra_voice_init(&s->residual,c->residual_bank,c->seed^UINT64_C(0xa6d34791),0,p->mix.residual_gain))return 0;
    vsl_init(e,48000,(uint32_t)c->seed);
    e->target=e->smooth=vsl_default_params(c->profile);
    vsl_drive_reset(&e->drive,c->profile);
    amounts(p,aux);if(!da_voice_init(&s->auxiliary,e,aux))return 0;
    ad_control_apply(e,p);
    e->smooth.width=p->mix.width;e->smooth.space=p->mix.room;e->smooth.perspective=p->mix.perspective;
    e->spatial.propagation.mix=p->mix.propagation;
    s->owner=e;s->config=*c;s->target=*p;
    s->gain=p->mix.gain;s->event_gain=p->mix.event_gain;s->spatial_mix=p->mix.spatial;
    s->follow=1-exp(-1/(.018*48000));
    return 1;
}
int ad_render_set(AdRender *s,const AdControl *p) {
    double aux[DA_LAYERS];
    if (!s||!s->owner||!ad_control_valid(p,s->config.channels)||(!s->config.residual_bank&&p->mix.residual_gain>0)||
        (!s->config.startup_profile&&p->mix.startup_gain>0)||(!s->config.catch_profile&&p->mix.catch_gain>0)||
        (!s->config.resonant_bank&&p->mix.resonant_gain>0)||(!s->config.recipe_bank&&p->mix.coherent_low_gain>0)) return 0;
    if(s->config.resonant_bank&&!drs_voice_set(&s->resonant,p->mix.resonant_gain))return 0;
    if(s->config.recipe_bank&&!drc_voice_set(&s->recipe,p->mix.coherent_low_gain))return 0;
    amounts(p,aux);da_voice_set(&s->auxiliary,aux);
    s->target=*p;hb_mix_set(&s->body,p->mix.body_mix);ad_control_apply(s->owner,p);return 1;
}
static int process(AdRender *s,float *out,unsigned frames,const AdCapture *cap) {
    unsigned n;
    AdCapture none={0};
    VslEngine *e;
    if (!s||!s->owner||(frames&&!out)) return 0;
    if (!cap) cap=&none;
    e=s->owner;
    for (n=0;n<frames;++n) {
        double raw[2],body_raw[2],residual_raw[2]={0},residual[2]={0},event,spatial[VSL_MAX_CHANNELS],dry[2],aux[2];
        double observation[2],bed[VSL_MAX_CHANNELS]={0};
        double starter[2]={0},starter_bed[VSL_MAX_CHANNELS]={0};
        double catch_delta[2]={0},catch_bed[VSL_MAX_CHANNELS]={0};
        DrsFrame resonance={0};double resonant[2]={0},sampled_phase;
        DrcFrame low={0};double coherent[2]={0};
        DsSourceFrame source={0};
        VslObjectFrame objects,residual_objects,body_objects={0},aux_raw,aux_objects;
        int c;
        if (s->frame%240==0) {
            vsl_drive_step(&e->drive,&e->target,.005);
            vsl_orchestrate(e,.005);vsl_events_update(e);
            /* No controller edits or derived-RPM latch in the host. */
            sa_voice_set(&s->dna,e->drive.rpm*s->config.root_per_rpm,s->target.mix.detail,1);
            if(s->config.residual_bank)ra_voice_set(&s->residual,e->drive.rpm*s->config.root_per_rpm,s->target.mix.residual_gain);
            vsl_scene_update(e,s->config.channels);
            if(s->config.startup_profile) {
                int gate=e->drive.lifecycle==VSL_CRANK;
                st_voice_set(&s->startup,gate,s->target.mix.startup_gain);
                if(gate)st_voice_position(&s->startup,fmin(1,e->drive.life_seconds/vsl_lifecycle_profile(s->config.profile)->crank_seconds));
            }
            if(s->config.catch_profile) {
                const VslLifecycleProfile *lp=vsl_lifecycle_profile(s->config.profile);
                int gate=e->drive.lifecycle==VSL_CATCH;
                double u=gate?fmin(1,e->drive.life_seconds/(lp->catch_rise_seconds+lp->catch_settle_seconds)):0;
                cb_voice_set(&s->catch_bloom,gate,u,s->target.mix.catch_gain);
            }
        }
        sampled_phase=s->dna.phase;
        if(s->config.recipe_bank) {
            double shape[SD_MAX_HARMONICS];
            if(!drc_shape(s->config.recipe_bank,&s->dna,s->config.resonant_bank?&s->resonant:NULL,shape)||
               !sa_voice_tick_shaped_body(&s->dna,&s->body_band,shape,1,raw,body_raw))return 0;
            if(!drc_voice_tick(&s->recipe,&s->dna,sampled_phase,&low))return 0;
        } else if(!sa_voice_tick_body(&s->dna,&s->body_band,raw,body_raw))return 0;
        if(s->config.resonant_bank&&!drs_voice_tick(&s->resonant,&s->dna,sampled_phase,&resonance))return 0;
        if(s->config.residual_bank)ra_voice_tick(&s->residual,residual,residual_raw);
        s->envelope+=s->follow*(e->voice.dna_gain-s->envelope);
        s->low_envelope+=s->follow*(e->voice.body_gain-s->low_envelope);
        s->gain+=s->follow*(s->target.mix.gain-s->gain);
        s->event_gain+=s->follow*(s->target.mix.event_gain-s->event_gain);
        s->spatial_mix+=s->follow*(s->target.mix.spatial-s->spatial_mix);
        e->smooth.width+=s->follow*(s->target.mix.width-e->smooth.width);
        e->smooth.space+=s->follow*(s->target.mix.room-e->smooth.space);
        e->smooth.perspective+=s->follow*(s->target.mix.perspective-e->smooth.perspective);
        if(s->config.startup_profile) {
            VslEventFrame parts;vsl_events_tick_parts(e,&parts);event=parts.transients*s->event_gain;
            st_voice_process(&s->startup,starter,NULL,1);
        } else event=vsl_events_tick(e)*s->event_gain;
        da_voice_tick(&s->auxiliary,e,&aux_raw,&aux_objects);da_stereo(&aux_objects,aux);
        hb_mix_tick(&s->body,raw,body_raw,s->envelope,e->voice.body_gain,source.dna,source.low);
        if(s->config.catch_profile) {
            /* Full enveloped DNA before complementary body redistribution:
               body amount must not remove input from this independent layer. */
            double input[2]={raw[0]*s->envelope,raw[1]*s->envelope};
            cb_voice_process(&s->catch_bloom,input,catch_delta,1);
        }
        for (c=0;c<2;++c) {
            residual[c]*=s->envelope;
            resonant[c]=resonance.output[c]*s->envelope;
            coherent[c]=low.output[c]*s->low_envelope;
            /* Explicit bypass preserves former output at exactly zero amount. */
            dry[c]=(source.dna[c]+event)*s->gain;
            if(residual[c]!=0)dry[c]=(source.dna[c]+residual[c]+event)*s->gain;
            if(source.low[c]!=0)dry[c]=(source.dna[c]+source.low[c]+residual[c]+event)*s->gain;
            if(aux[c]!=0)dry[c]+=aux[c]*s->gain;
            if(starter[c]!=0)dry[c]+=starter[c]*s->gain;
            if(catch_delta[c]!=0)dry[c]+=catch_delta[c]*s->gain;
            if(resonant[c]!=0)dry[c]+=resonant[c]*s->gain;
            if(coherent[c]!=0)dry[c]+=coherent[c]*s->gain;
            observation[c]=source.dna[c]+source.low[c]+residual[c];
            if(resonant[c]!=0)observation[c]+=resonant[c];
            if(coherent[c]!=0)observation[c]+=coherent[c];
        }
        memset(&objects,0,sizeof objects);memset(&residual_objects,0,sizeof residual_objects);
        if(s->config.scene_mode==AD_SCENE_OBJECTS) {
            DsSourceFrame upper=source;upper.low[0]=upper.low[1]=0;
            ds_route_frame(&upper,s->config.projection,s->config.route,&objects);
            body_objects.sample[VSL_BODY]=s->config.projection==DS_OBSERVE_LEFT?source.low[0]:
                s->config.projection==DS_OBSERVE_RIGHT?source.low[1]:.5*(source.low[0]+source.low[1]);
            if(body_objects.sample[VSL_BODY]!=0)objects.sample[VSL_BODY]=body_objects.sample[VSL_BODY];
            if(s->config.recipe_bank) {
                double v=s->config.projection==DS_OBSERVE_LEFT?coherent[0]:
                    s->config.projection==DS_OBSERVE_RIGHT?coherent[1]:.5*(coherent[0]+coherent[1]);
                if(v!=0)objects.sample[VSL_BODY]+=v;
            }
        }
        if(s->config.scene_mode==AD_SCENE_OBJECTS) {
            DsSourceFrame separate={0};separate.dna[0]=residual[0];separate.dna[1]=residual[1];
            ds_route_frame(&separate,s->config.projection,s->config.route,&residual_objects);
            for(c=0;c<VSL_OBJECTS;++c)if(residual_objects.sample[c]!=0)objects.sample[c]+=residual_objects.sample[c];
            if(s->config.resonant_bank) {
                VslObjectFrame detail_objects;separate.dna[0]=resonant[0];separate.dna[1]=resonant[1];
                ds_route_frame(&separate,s->config.projection,s->config.route,&detail_objects);
                for(c=0;c<VSL_OBJECTS;++c)if(detail_objects.sample[c]!=0)objects.sample[c]+=detail_objects.sample[c];
            }
        }
        objects.sample[VSL_EVENT]=event;
        for(c=0;c<VSL_OBJECTS;++c)if(aux_objects.sample[c]!=0)objects.sample[c]+=aux_objects.sample[c];
        /* Render spatial once from the same ongoing voice, also in dry mode,
           so switches cannot restart source, delay lines or reflection tails. */
        vsl_scene_tick(e,&objects,spatial,s->config.channels);
        if(s->config.scene_mode==AD_SCENE_STEREO_BED)
            sb_route(&s->bed_layout,observation,e->smooth.width,bed);
        if(s->config.startup_profile)sb_route(&s->bed_layout,starter,e->smooth.width,starter_bed);
        if(s->config.catch_profile)sb_route(&s->bed_layout,catch_delta,e->smooth.width,catch_bed);
        for (c=0;c<s->config.channels;++c) {
            double x=spatial[c]*s->gain;
            if(s->config.scene_mode==AD_SCENE_STEREO_BED)x=(spatial[c]+bed[c])*s->gain;
            if(starter_bed[c]!=0)x+=starter_bed[c]*s->gain;
            if(catch_bed[c]!=0)x+=catch_bed[c]*s->gain;
            if (s->config.channels==2) x=dry[c]+s->spatial_mix*(x-dry[c]);
            out[n*s->config.channels+c]=(float)x;
        }
        for (c=0;c<2;++c) {
            if (cap->dna_raw) cap->dna_raw[2*n+c]=(float)raw[c];
            if (cap->dna) cap->dna[2*n+c]=(float)source.dna[c];
            if (cap->dry) cap->dry[2*n+c]=(float)dry[c];
            if (cap->residual_raw) cap->residual_raw[2*n+c]=(float)residual_raw[c];
            if (cap->residual) cap->residual[2*n+c]=(float)residual[c];
            if (cap->body_raw) cap->body_raw[2*n+c]=(float)body_raw[c];
            if (cap->body) cap->body[2*n+c]=(float)source.low[c];
            if (cap->aux) cap->aux[2*n+c]=(float)aux[c];
            if (cap->observation)cap->observation[2*n+c]=(float)observation[c];
            if (cap->startup)cap->startup[2*n+c]=(float)starter[c];
            if (cap->catch_bloom)cap->catch_bloom[2*n+c]=(float)catch_delta[c];
            if (cap->resonant_raw)cap->resonant_raw[2*n+c]=(float)resonance.raw[c];
            if (cap->resonant)cap->resonant[2*n+c]=(float)resonant[c];
            if (cap->coherent_low_raw)cap->coherent_low_raw[2*n+c]=(float)low.raw[c];
            if (cap->coherent_low)cap->coherent_low[2*n+c]=(float)coherent[c];
        }
        if(cap->bed)for(c=0;c<s->config.channels;++c)cap->bed[n*s->config.channels+c]=(float)bed[c];
        if (cap->events) cap->events[n]=(float)event;
        if (cap->objects) for (c=0;c<VSL_OBJECTS;++c) cap->objects[n*VSL_OBJECTS+c]=(float)objects.sample[c];
        if (cap->residual_objects) for(c=0;c<VSL_OBJECTS;++c)cap->residual_objects[n*VSL_OBJECTS+c]=(float)residual_objects.sample[c];
        if (cap->body_objects) for(c=0;c<VSL_OBJECTS;++c)cap->body_objects[n*VSL_OBJECTS+c]=(float)body_objects.sample[c];
        if (cap->aux_raw) for(c=0;c<VSL_OBJECTS;++c)cap->aux_raw[n*VSL_OBJECTS+c]=(float)aux_raw.sample[c];
        if (cap->aux_objects) for(c=0;c<VSL_OBJECTS;++c)cap->aux_objects[n*VSL_OBJECTS+c]=(float)aux_objects.sample[c];
        if (cap->telemetry) {
            AdTelemetry *t=&cap->telemetry[n];
            t->frame=s->frame;t->rpm=e->drive.rpm;t->speed=e->drive.speed_kph;t->load=e->drive.load;
            t->root_hz=s->dna.root_hz;t->blend=s->dna.blend;t->envelope=s->envelope;
            t->lower=s->dna.lower;t->upper=s->dna.upper;t->coverage=s->dna.coverage;
            t->gear=e->drive.gear;t->lifecycle=e->drive.lifecycle;t->operating=e->drive.operating;
            t->shifts=e->drive.shift_events;t->overruns=e->drive.overrun_events;t->hits=e->events.hits;
            t->residual_gain=s->config.residual_bank?s->residual.gain:0;
            t->body_mix=s->body.amount;t->body_envelope=s->body.envelope;
            t->auxiliary_rpm=e->control.rpm;t->firing=e->excitation.firing;t->fuel_mode=e->drive.fuel.mode;
            t->rotating_strikes=e->mechanical.rotating_strikes;t->fired_strikes=e->mechanical.fired_strikes;
            t->resonant_support=resonance.support;t->resonant_gain=s->config.resonant_bank?s->resonant.amount:0;
            t->coherent_low_support=low.support;t->coherent_low_gain=s->config.recipe_bank?s->recipe.amount:0;
            t->coherent_low_envelope=s->low_envelope;
        }
        ++s->frame;++e->frame;
    }
    return 1;
}
int ad_render_process(AdRender *s,float *out,unsigned frames,const AdCapture *cap) {
    RnScope scope=rn_scope_enter();
    int result=process(s,out,frames,cap);
    rn_scope_leave(scope);return result;
}
