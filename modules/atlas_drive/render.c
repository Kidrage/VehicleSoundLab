#include "render.h"
#include "core/engine.h"
#include "core/modules.h"
#include "drive/drive.h"
#include "spatial/scene.h"
#include <math.h>
#include <string.h>

int ad_render_init(AdRender *s,VslEngine *e,const AdConfig *c,const AdControl *p) {
    unsigned a;
    if (!s||!e||!c||!c->bank||!c->bank->count||c->bank->count>SA_MAX_ANCHORS||!ad_control_valid(p,c->channels)||
        c->profile<0||c->profile>=VSL_PROFILE_COUNT||!isfinite(c->root_per_rpm)||
        c->root_per_rpm<=0||c->root_per_rpm>.1||!ds_routing_valid(c->projection,c->route)||
        (!c->residual_bank&&p->mix.residual_gain>0)) return 0;
    if(c->residual_bank) {
        if(!ra_bank_valid(c->residual_bank)||c->residual_bank->count!=c->bank->count)return 0;
        for(a=0;a<c->bank->count;++a)if(!c->bank->profile[a]||fabs(c->residual_bank->root[a]-c->bank->profile[a]->base_hz)>1e-8)return 0;
    }
    memset(s,0,sizeof *s);
    if (!sa_voice_init(&s->dna,c->bank,c->seed,0,p->mix.detail,1)) return 0;
    s->body_band=hb_band_default();
    /* Engineering voicing scale, not a measured structural transfer. */
    if(!hb_mix_init(&s->body,48000,p->mix.body_mix,1.6))return 0;
    if(c->residual_bank&&!ra_voice_init(&s->residual,c->residual_bank,c->seed^UINT64_C(0xa6d34791),0,p->mix.residual_gain))return 0;
    vsl_init(e,48000,(uint32_t)c->seed);
    e->target=e->smooth=vsl_default_params(c->profile);
    vsl_drive_reset(&e->drive,c->profile);
    ad_control_apply(e,p);
    e->smooth.width=p->mix.width;e->smooth.space=p->mix.room;e->smooth.perspective=p->mix.perspective;
    e->spatial.propagation.mix=p->mix.propagation;
    s->owner=e;s->config=*c;s->target=*p;
    s->gain=p->mix.gain;s->event_gain=p->mix.event_gain;s->spatial_mix=p->mix.spatial;
    s->follow=1-exp(-1/(.018*48000));
    return 1;
}
int ad_render_set(AdRender *s,const AdControl *p) {
    if (!s||!s->owner||!ad_control_valid(p,s->config.channels)||(!s->config.residual_bank&&p->mix.residual_gain>0)) return 0;
    s->target=*p;hb_mix_set(&s->body,p->mix.body_mix);ad_control_apply(s->owner,p);return 1;
}
int ad_render_process(AdRender *s,float *out,unsigned frames,const AdCapture *cap) {
    unsigned n;
    AdCapture none={0};
    VslEngine *e;
    if (!s||!s->owner||(frames&&!out)) return 0;
    if (!cap) cap=&none;
    e=s->owner;
    for (n=0;n<frames;++n) {
        double raw[2],body_raw[2],residual_raw[2]={0},residual[2]={0},event,spatial[VSL_MAX_CHANNELS],dry[2];
        DsSourceFrame source={0};
        VslObjectFrame objects,residual_objects,body_objects={0};
        int c;
        if (s->frame%240==0) {
            vsl_drive_step(&e->drive,&e->target,.005);
            vsl_orchestrate(e,.005);vsl_events_update(e);
            /* No controller edits or derived-RPM latch in the host. */
            sa_voice_set(&s->dna,e->drive.rpm*s->config.root_per_rpm,s->target.mix.detail,1);
            if(s->config.residual_bank)ra_voice_set(&s->residual,e->drive.rpm*s->config.root_per_rpm,s->target.mix.residual_gain);
            vsl_scene_update(e,s->config.channels);
        }
        if(!sa_voice_tick_body(&s->dna,&s->body_band,raw,body_raw))return 0;
        if(s->config.residual_bank)ra_voice_tick(&s->residual,residual,residual_raw);
        s->envelope+=s->follow*(e->voice.dna_gain-s->envelope);
        s->gain+=s->follow*(s->target.mix.gain-s->gain);
        s->event_gain+=s->follow*(s->target.mix.event_gain-s->event_gain);
        s->spatial_mix+=s->follow*(s->target.mix.spatial-s->spatial_mix);
        e->smooth.width+=s->follow*(s->target.mix.width-e->smooth.width);
        e->smooth.space+=s->follow*(s->target.mix.room-e->smooth.space);
        e->smooth.perspective+=s->follow*(s->target.mix.perspective-e->smooth.perspective);
        event=vsl_events_tick(e)*s->event_gain;
        hb_mix_tick(&s->body,raw,body_raw,s->envelope,e->voice.body_gain,source.dna,source.low);
        for (c=0;c<2;++c) {
            residual[c]*=s->envelope;
            /* Explicit bypass preserves former output at exactly zero amount. */
            dry[c]=(source.dna[c]+event)*s->gain;
            if(residual[c]!=0)dry[c]=(source.dna[c]+residual[c]+event)*s->gain;
            if(source.low[c]!=0)dry[c]=(source.dna[c]+source.low[c]+residual[c]+event)*s->gain;
        }
        {
            DsSourceFrame upper=source;upper.low[0]=upper.low[1]=0;
            ds_route_frame(&upper,s->config.projection,s->config.route,&objects);
            body_objects.sample[VSL_BODY]=s->config.projection==DS_OBSERVE_LEFT?source.low[0]:
                s->config.projection==DS_OBSERVE_RIGHT?source.low[1]:.5*(source.low[0]+source.low[1]);
            if(body_objects.sample[VSL_BODY]!=0)objects.sample[VSL_BODY]=body_objects.sample[VSL_BODY];
        }
        {
            DsSourceFrame separate={0};separate.dna[0]=residual[0];separate.dna[1]=residual[1];
            ds_route_frame(&separate,s->config.projection,s->config.route,&residual_objects);
            for(c=0;c<VSL_OBJECTS;++c)if(residual_objects.sample[c]!=0)objects.sample[c]+=residual_objects.sample[c];
        }
        objects.sample[VSL_EVENT]=event;
        /* Render spatial once from the same ongoing voice, also in dry mode,
           so switches cannot restart source, delay lines or reflection tails. */
        vsl_scene_tick(e,&objects,spatial,s->config.channels);
        for (c=0;c<s->config.channels;++c) {
            double x=spatial[c]*s->gain;
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
        }
        if (cap->events) cap->events[n]=(float)event;
        if (cap->objects) for (c=0;c<VSL_OBJECTS;++c) cap->objects[n*VSL_OBJECTS+c]=(float)objects.sample[c];
        if (cap->residual_objects) for(c=0;c<VSL_OBJECTS;++c)cap->residual_objects[n*VSL_OBJECTS+c]=(float)residual_objects.sample[c];
        if (cap->body_objects) for(c=0;c<VSL_OBJECTS;++c)cap->body_objects[n*VSL_OBJECTS+c]=(float)body_objects.sample[c];
        if (cap->telemetry) {
            AdTelemetry *t=&cap->telemetry[n];
            t->frame=s->frame;t->rpm=e->drive.rpm;t->speed=e->drive.speed_kph;t->load=e->drive.load;
            t->root_hz=s->dna.root_hz;t->blend=s->dna.blend;t->envelope=s->envelope;
            t->lower=s->dna.lower;t->upper=s->dna.upper;t->coverage=s->dna.coverage;
            t->gear=e->drive.gear;t->lifecycle=e->drive.lifecycle;t->operating=e->drive.operating;
            t->shifts=e->drive.shift_events;t->overruns=e->drive.overrun_events;t->hits=e->events.hits;
            t->residual_gain=s->config.residual_bank?s->residual.gain:0;
            t->body_mix=s->body.amount;t->body_envelope=s->body.envelope;
        }
        ++s->frame;++e->frame;
    }
    return 1;
}
