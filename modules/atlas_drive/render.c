#include "render.h"
#include "core/engine.h"
#include "core/modules.h"
#include "drive/drive.h"
#include "spatial/scene.h"
#include <math.h>
#include <string.h>

int ad_render_init(AdRender *s,VslEngine *e,const AdConfig *c,const AdControl *p) {
    if (!s||!e||!c||!c->bank||!ad_control_valid(p,c->channels)||
        c->profile<0||c->profile>=VSL_PROFILE_COUNT||!isfinite(c->root_per_rpm)||
        c->root_per_rpm<=0||c->root_per_rpm>.1||!ds_routing_valid(c->projection,c->route)) return 0;
    memset(s,0,sizeof *s);
    if (!sa_voice_init(&s->dna,c->bank,c->seed,0,p->mix.detail,1)) return 0;
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
    if (!s||!s->owner||!ad_control_valid(p,s->config.channels)) return 0;
    s->target=*p;ad_control_apply(s->owner,p);return 1;
}
int ad_render_process(AdRender *s,float *out,unsigned frames,const AdCapture *cap) {
    unsigned n;
    AdCapture none={0};
    VslEngine *e;
    if (!s||!s->owner||(frames&&!out)) return 0;
    if (!cap) cap=&none;
    e=s->owner;
    for (n=0;n<frames;++n) {
        double raw[2],event,spatial[VSL_MAX_CHANNELS],dry[2];
        DsSourceFrame source={0};
        VslObjectFrame objects;
        int c;
        if (s->frame%240==0) {
            vsl_drive_step(&e->drive,&e->target,.005);
            vsl_orchestrate(e,.005);vsl_events_update(e);
            /* No controller edits or derived-RPM latch in the host. */
            sa_voice_set(&s->dna,e->drive.rpm*s->config.root_per_rpm,s->target.mix.detail,1);
            vsl_scene_update(e,s->config.channels);
        }
        sa_voice_tick(&s->dna,raw);
        s->envelope+=s->follow*(e->voice.dna_gain-s->envelope);
        s->gain+=s->follow*(s->target.mix.gain-s->gain);
        s->event_gain+=s->follow*(s->target.mix.event_gain-s->event_gain);
        s->spatial_mix+=s->follow*(s->target.mix.spatial-s->spatial_mix);
        e->smooth.width+=s->follow*(s->target.mix.width-e->smooth.width);
        e->smooth.space+=s->follow*(s->target.mix.room-e->smooth.space);
        e->smooth.perspective+=s->follow*(s->target.mix.perspective-e->smooth.perspective);
        event=vsl_events_tick(e)*s->event_gain;
        for (c=0;c<2;++c) { source.dna[c]=raw[c]*s->envelope;dry[c]=(source.dna[c]+event)*s->gain; }
        ds_route_frame(&source,s->config.projection,s->config.route,&objects);
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
        }
        if (cap->events) cap->events[n]=(float)event;
        if (cap->objects) for (c=0;c<VSL_OBJECTS;++c) cap->objects[n*VSL_OBJECTS+c]=(float)objects.sample[c];
        if (cap->telemetry) {
            AdTelemetry *t=&cap->telemetry[n];
            t->frame=s->frame;t->rpm=e->drive.rpm;t->speed=e->drive.speed_kph;t->load=e->drive.load;
            t->root_hz=s->dna.root_hz;t->blend=s->dna.blend;t->envelope=s->envelope;
            t->lower=s->dna.lower;t->upper=s->dna.upper;t->coverage=s->dna.coverage;
            t->gear=e->drive.gear;t->lifecycle=e->drive.lifecycle;t->operating=e->drive.operating;
            t->shifts=e->drive.shift_events;t->overruns=e->drive.overrun_events;t->hits=e->events.hits;
        }
        ++s->frame;++e->frame;
    }
    return 1;
}
