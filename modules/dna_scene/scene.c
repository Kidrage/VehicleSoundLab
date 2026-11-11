#include "scene.h"
#include "core/engine.h"
#include "spatial/scene.h"
#include <math.h>
#include <string.h>

static int unit(double x) { return isfinite(x) && x >= 0 && x <= 1; }

int ds_scene_control_valid(const DsSceneControl *c) {
    return c && ds_source_control_valid(&c->source) && unit(c->output_gain) &&
        unit(c->width) && unit(c->space) && unit(c->perspective) &&
        (c->propagation == 0 || c->propagation == 1);
}

int ds_scene_init(DsScene *s, VslEngine *e, const DsSceneConfig *c, const DsSceneControl *p) {
    if (!s || !e || !c || !ds_scene_control_valid(p) ||
        !ds_routing_valid(c->projection, c->route) || (c->channels != 2 && c->channels != 12)) return 0;
    memset(s, 0, sizeof *s);
    if (!ds_source_init(&s->source, &c->source, &p->source)) return 0;
    /* Only the spatial fields are ticked below. Legacy drive and sources stay idle. */
    vsl_init(e, 48000, 48271);
    e->smooth.width = p->width;
    e->smooth.space = p->space;
    e->smooth.perspective = p->perspective;
    e->target.propagation = p->propagation;
    e->spatial.propagation.mix = p->propagation;
    vsl_scene_update(e, c->channels);
    s->spatial_owner = e;
    s->projection = c->projection;
    s->route = c->route;
    s->channels = c->channels;
    s->target = *p;
    s->output_gain = p->output_gain;
    s->follow = 1 - exp(-1 / (.018 * 48000));
    return 1;
}

int ds_scene_set(DsScene *s, const DsSceneControl *c) {
    if (!s || !s->spatial_owner || !ds_scene_control_valid(c)) return 0;
    if (!ds_source_set(&s->source, &c->source)) return 0;
    s->target = *c;
    return 1;
}

int ds_scene_process(DsScene *s, float *out, unsigned frames, const DsCapture *capture) {
    unsigned n;
    DsCapture none = {0};
    VslEngine *e;
    if (!s || !s->spatial_owner || (frames && !out)) return 0;
    if (!capture) capture = &none;
    e = s->spatial_owner;
    for (n = 0; n < frames; ++n) {
        DsSourceFrame source;
        VslObjectFrame objects;
        double spatial[VSL_MAX_CHANNELS];
        int c;
        ds_source_tick(&s->source, &source);
        ds_route_frame(&source, s->projection, s->route, &objects);
#define FOLLOW(field) e->smooth.field += s->follow * (s->target.field - e->smooth.field)
        FOLLOW(width); FOLLOW(space); FOLLOW(perspective);
#undef FOLLOW
        s->output_gain += s->follow * (s->target.output_gain - s->output_gain);
        e->target.propagation = s->target.propagation;
        if (s->frame % 240 == 0) vsl_scene_update(e, s->channels);
        vsl_scene_tick(e, &objects, spatial, s->channels);
        for (c = 0; c < s->channels; ++c) out[n * s->channels + c] = (float)(spatial[c] * s->output_gain);
        for (c = 0; c < 2; ++c) {
            if (capture->dna_raw) capture->dna_raw[n * 2 + c] = (float)source.dna_raw[c];
            if (capture->low_raw) capture->low_raw[n * 2 + c] = (float)source.low_raw[c];
            if (capture->dna) capture->dna[n * 2 + c] = (float)source.dna[c];
            if (capture->low) capture->low[n * 2 + c] = (float)source.low[c];
            if (capture->dry) capture->dry[n * 2 + c] = (float)((source.dna[c] + source.low[c]) * s->output_gain);
        }
        if (capture->objects) for (c = 0; c < VSL_OBJECTS; ++c)
            capture->objects[n * VSL_OBJECTS + c] = (float)objects.sample[c];
        ++s->frame;
    }
    return 1;
}
