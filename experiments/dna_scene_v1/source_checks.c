#include "checks.h"
#include <math.h>
#include <stdlib.h>
#include <string.h>

void source_checks(const SdProfile *dna, const SdProfile *low) {
    DsSource *s = calloc(1, sizeof *s), *without = calloc(1, sizeof *without);
    SdVoice *d = calloc(1, sizeof *d), *l = calloc(1, sizeof *l);
    DsSceneConfig config = test_config(dna, low);
    DsSourceConfig only = config.source;
    DsSceneControl control = test_control();
    DsSourceControl p = control.source;
    DsSourceFrame frame, no_low;
    unsigned n;
    CHECK(s && without && d && l, "source allocations outside audio");
    if (!s || !without || !d || !l) goto done;
    CHECK(ds_source_init(s, &config.source, &p), "pair initializes");
    only.low = NULL;
    CHECK(ds_source_init(without, &only, &p), "optional low initializes");
    CHECK(sd_voice_init(d, dna, 48271, 1, 1, 1) && sd_voice_init(l, low, 48271, 1, 1, 1), "independent reference voices");
    for (n = 0; n < 6000; ++n) {
        double dr[2], lr[2];
        if (n == 511 || n == 2021) {
            p.pitch = n == 511 ? .9 : 1.1;
            p.dna_detail = n == 511 ? .6 : 1;
            p.low_detail = n == 511 ? .3 : .8;
            p.low_gain = n == 511 ? 0 : 1;
            CHECK(ds_source_set(s, &p) && ds_source_set(without, &p), "source control transition");
            sd_voice_set(d, p.pitch, p.dna_detail, 1);
            sd_voice_set(l, p.pitch, p.low_detail, 1);
        }
        ds_source_tick(s, &frame); ds_source_tick(without, &no_low);
        sd_voice_process(d, dr, 1); sd_voice_process(l, lr, 1);
        CHECK(!memcmp(frame.dna_raw, dr, sizeof dr), "DNA is bit-identical to standalone through parameter changes");
        CHECK(!memcmp(frame.low_raw, lr, sizeof lr), "LF is bit-identical to standalone even when muted");
        CHECK(!memcmp(frame.dna_raw, no_low.dna_raw, sizeof dr), "optional low never changes DNA");
        CHECK(no_low.low[0] == 0 && no_low.low[1] == 0, "missing low remains silent");
        CHECK(s->dna.oscillator.phase == s->low.oscillator.phase && s->dna.texture.fraction == s->low.texture.fraction, "pair keeps the same acoustic clock");
        CHECK(frame.low[0] == frame.low_raw[0] * s->low_scale * s->low_gain, "LF calibration and mute gain are explicit");
    }
    {
        uint64_t at = s->frame;
        double pitch = s->dna.pitch_target;
        DsSourceControl before = s->target;
        p.pitch = NAN;
        CHECK(!ds_source_set(s, &p), "reject nonfinite pitch");
        CHECK(s->frame == at && s->dna.pitch_target == pitch && !memcmp(&before, &s->target, sizeof before), "invalid source control is atomic");
        p = control.source; p.low_gain = 1.01;
        CHECK(!ds_source_set(s, &p), "reject gain outside contract");
    }
    {
        SdProfile *different = malloc(sizeof *different);
        CHECK(different != NULL, "allocate incompatible model outside audio");
        if (different) {
            *different = *low; different->base_hz += 1;
            only.low = different;
            CHECK(!ds_source_init(without, &only, &control.source), "reject incompatible LF acoustic coordinate");
            free(different);
        }
    }
    {
        DsSourceFrame values = {{0}, {0}, {2, 4}, {1, 2}};
        VslObjectFrame o;
        int projection, route, i;
        for (projection = 0; projection < 3; ++projection) for (route = 0; route < 3; ++route) {
            double mono = projection == 0 ? 3 : projection == 1 ? 6 : 4.5;
            ds_route_frame(&values, (DsProjection)projection, (DsRoute)route, &o);
            CHECK(o.sample[0] + o.sample[1] == mono, "outlet projection preserves coherent mono sum");
            if (!route) CHECK(o.sample[0] == .5 * mono && o.sample[1] == .5 * mono, "paired outlets split amplitude");
            else CHECK(o.sample[route == DS_ROUTE_LEFT ? 0 : 1] == mono, "single outlet selection");
            for (i = 2; i < VSL_OBJECTS; ++i) CHECK(o.sample[i] == 0, "unmodeled source objects stay empty");
        }
        CHECK(!ds_routing_valid((DsProjection)-1, DS_ROUTE_PAIR), "reject invalid observation selection");
    }
done:
    free(s); free(without); free(d); free(l);
}
