#include "checks.h"
#include <math.h>
#include <stdlib.h>
#include <string.h>
#define BLOCK 256

void spatial_checks(const SdProfile *dna, const SdProfile *low) {
    DsScene *a = calloc(1, sizeof *a), *b = calloc(1, sizeof *b);
    VslEngine *ea = calloc(1, sizeof *ea), *eb = calloc(1, sizeof *eb);
    DsSceneConfig ca = test_config(dna, low), cb = ca;
    DsSceneControl pa = test_control(), pb = pa;
    static float ao[BLOCK * 12], bo[BLOCK * 12], ad[BLOCK * 2], bd[BLOCK * 2];
    static float al[BLOCK * 2], bl[BLOCK * 2], ast[BLOCK * 10], bst[BLOCK * 10];
    DsCapture ac = {ad, al, NULL, NULL, NULL, ast}, bc = {bd, bl, NULL, NULL, NULL, bst};
    unsigned n, k;
    CHECK(a && b && ea && eb, "scene allocations outside audio");
    if (!a || !b || !ea || !eb) goto done;
    cb.channels = 12; pb.space = .65; pb.perspective = .4; pb.propagation = 1;
    CHECK(ds_scene_init(a, ea, &ca, &pa) && ds_scene_init(b, eb, &cb, &pb), "two spatial layouts initialize");
    for (n = 0; n < 20; ++n) {
        if (n == 5) {
            pa.source.pitch = pb.source.pitch = 1.1;
            pa.source.low_gain = pb.source.low_gain = .4;
            CHECK(ds_scene_set(a, &pa) && ds_scene_set(b, &pb), "source controls shared across layouts");
        }
        CHECK(ds_scene_process(a, ao, BLOCK, &ac) && ds_scene_process(b, bo, BLOCK, &bc), "process both layouts");
        CHECK(!memcmp(ad, bd, sizeof ad) && !memcmp(al, bl, sizeof al), "layout, cabin, room and propagation never affect raw sources");
        CHECK(!memcmp(ast, bst, sizeof ast), "layout and space never affect source objects");
        for (k = 0; k < BLOCK * 12; ++k) CHECK(isfinite(bo[k]), "spatial output remains finite");
    }
    CHECK(ea->frame == 0 && eb->frame == 0 && ea->drive.running_seconds == 0 && eb->dna.real[0] == 0, "legacy driving and old DNA never run");
    {
        DsSceneControl invalid = pa, before = a->target;
        uint64_t frame = a->frame;
        invalid.width = NAN;
        CHECK(!ds_scene_set(a, &invalid) && a->frame == frame && !memcmp(&before, &a->target, sizeof before), "invalid scene control leaves target and clock unchanged");
        invalid = pa; invalid.propagation = 2;
        CHECK(!ds_scene_set(a, &invalid), "reject invalid propagation switch");
        CHECK(!ds_scene_process(a, NULL, 1, NULL) && a->frame == frame, "missing output does not advance time");
        CHECK(ds_scene_process(a, NULL, 0, NULL) && a->frame == frame, "empty block is a no-op");
    }
    /* One long call versus irregular host block boundaries, including room history. */
    {
        const unsigned total = 2401;
        float *whole = malloc(total * 2 * sizeof *whole), *split = malloc(total * 2 * sizeof *split);
        unsigned at = 0;
        CHECK(whole && split, "allocate block invariance output");
        pa = test_control(); pa.space = .65; pa.propagation = 1;
        CHECK(ds_scene_init(a, ea, &ca, &pa) && ds_scene_init(b, eb, &ca, &pa), "reset for block invariance");
        if (whole && split) {
            CHECK(ds_scene_process(a, whole, total, NULL), "single host block");
            while (at < total) {
                unsigned count = at % 317 + 1;
                if (count > total - at) count = total - at;
                CHECK(ds_scene_process(b, split + at * 2, count, NULL), "irregular host block"); at += count;
            }
            CHECK(!memcmp(whole, split, total * 2 * sizeof *whole), "host block boundaries are bit-invariant");
        }
        free(whole); free(split);
    }
    /* Exterior listener is centred. Single outlets mirror, with and without propagation. */
    for (k = 0; k < 2; ++k) {
        double maximum = 0;
        ca.route = DS_ROUTE_LEFT; cb = ca; cb.route = DS_ROUTE_RIGHT;
        pa = test_control(); pa.propagation = (int)k;
        CHECK(ds_scene_init(a, ea, &ca, &pa) && ds_scene_init(b, eb, &cb, &pa), "mirror scenes initialize");
        for (n = 0; n < 16; ++n) {
            ds_scene_process(a, ao, BLOCK, NULL); ds_scene_process(b, bo, BLOCK, NULL);
            for (unsigned i = 0; i < BLOCK; ++i) {
                maximum = fmax(maximum, fabs(ao[2*i] - bo[2*i+1]));
                maximum = fmax(maximum, fabs(ao[2*i+1] - bo[2*i]));
            }
        }
        CHECK(maximum < 1e-7, "left/right outlets mirror ear outputs");
    }
    ca.route = DS_ROUTE_PAIR; pa = test_control();
    CHECK(ds_scene_init(a, ea, &ca, &pa), "symmetric pair initializes");
    for (n = 0; n < 5; ++n) {
        ds_scene_process(a, ao, BLOCK, NULL);
        for (k = 0; k < BLOCK; ++k) CHECK(fabs(ao[k*2] - ao[k*2+1]) < 1e-7, "symmetric dry projection does not manufacture stereo");
    }
    pa.width = 0; pa.space = 1; pa.perspective = .6; pa.propagation = 1;
    CHECK(ds_scene_init(a, ea, &ca, &pa), "mono with asymmetric room/cabin initializes");
    for (n = 0; n < 12; ++n) {
        ds_scene_process(a, ao, BLOCK, NULL);
        for (k = 0; k < BLOCK; ++k) CHECK(ao[k*2] == ao[k*2+1], "width zero folds all spatial tails to mono");
    }
    ca.channels = 12; pa = test_control();
    CHECK(ds_scene_init(a, ea, &ca, &pa), "dry bed initializes");
    for (n = 0; n < 12; ++n) {
        ds_scene_process(a, ao, BLOCK, NULL);
        for (k = 0; k < BLOCK; ++k) for (unsigned c = 8; c < 12; ++c)
            CHECK(ao[k*12+c] == 0, "height channels contain no dry source");
    }
    pa.space = .65; CHECK(ds_scene_set(a, &pa), "enable room send");
    {
        double height_energy = 0;
        for (n = 0; n < 12; ++n) {
            ds_scene_process(a, ao, BLOCK, NULL);
            for (k = 0; k < BLOCK; ++k) for (unsigned c = 8; c < 12; ++c)
                height_energy += ao[k*12+c] * ao[k*12+c];
        }
        CHECK(height_energy > 1e-8, "height channels receive room reflections");
    }
    ca.channels = 6;
    CHECK(!ds_scene_init(a, ea, &ca, &pa), "reject unsupported output layout");
done:
    free(a); free(b); free(ea); free(eb);
}
