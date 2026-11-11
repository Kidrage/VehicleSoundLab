#include "render.h"
#include <math.h>
#include <string.h>

int smo_control_valid(const SmoControl *c) {
    return c && ds_scene_control_valid(&c->scene) && (c->spatial == 0 || c->spatial == 1);
}

int smo_render_init(SmoRender *s, VslEngine *e, const DsSceneConfig *config, const SmoControl *c) {
    if (!s || !config || config->channels != 2 || !smo_control_valid(c)) return 0;
    memset(s, 0, sizeof *s);
    if (!ds_scene_init(&s->scene, e, config, &c->scene)) return 0;
    s->target = *c;
    s->spatial_mix = c->spatial;
    s->follow = 1 - exp(-1 / (.018 * 48000));
    return 1;
}

int smo_render_set(SmoRender *s, const SmoControl *c) {
    if (!s || !smo_control_valid(c) || !ds_scene_set(&s->scene, &c->scene)) return 0;
    s->target = *c;
    return 1;
}

int smo_render_process(SmoRender *s, float *out, unsigned frames, int stop, const SmoCapture *capture) {
    unsigned at = 0;
    if (!s || !s->scene.spatial_owner || (frames && !out)) return 0;
    if (stop && frames) s->stopping = 1;
    while (at < frames) {
        float dry[1024], spatial[1024];
        unsigned n = frames - at, i, c;
        DsCapture caps = {0};
        if (n > 512) n = 512;
        caps.dry = dry;
        if (capture) {
            caps.dna_raw = capture->dna_raw ? capture->dna_raw + at * 2 : NULL;
            caps.low_raw = capture->low_raw ? capture->low_raw + at * 2 : NULL;
        }
        if (!ds_scene_process(&s->scene, spatial, n, &caps)) return 0;
        for (i = 0; i < n; ++i) {
            double envelope = s->onset < 240 ? s->onset++ / 239. : 1;
            s->spatial_mix += s->follow * (s->target.spatial - s->spatial_mix);
            if (fabs(s->target.spatial - s->spatial_mix) < 1e-12) s->spatial_mix = s->target.spatial;
            if (s->stopping) {
                if (s->release < 480) ++s->release;
                envelope *= 1 - s->release / 480.;
            }
            for (c = 0; c < 2; ++c) {
                unsigned sample = i * 2 + c;
                double mix = dry[sample] + (spatial[sample] - (double)dry[sample]) * s->spatial_mix;
                out[(at + i) * 2 + c] = (float)(mix * envelope);
                if (capture && capture->dry) capture->dry[(at + i) * 2 + c] = dry[sample];
                if (capture && capture->spatial) capture->spatial[(at + i) * 2 + c] = spatial[sample];
            }
        }
        at += n;
    }
    return 1;
}
