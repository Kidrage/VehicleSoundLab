#include "recipe.h"
#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
static int failures;
static SdProfile dna, low;
#define CHECK(x, message) do { if (!(x)) { fprintf(stderr, "FAIL: %s\n", message); ++failures; } } while (0)

int main(int argc, char **argv) {
    SmoRender *a = calloc(1, sizeof *a), *b = calloc(1, sizeof *b);
    VslEngine *ea = calloc(1, sizeof *ea), *eb = calloc(1, sizeof *eb);
    DsSceneConfig config; SmoControl c = smo_recipe_control(), space = c;
    static float ao[2048], bo[2048], ad[2048], bd[2048], al[2048], bl[2048], dry[2048], spatial[2048];
    SmoCapture ac = {ad, al, dry, NULL}, bc = {bd, bl, NULL, spatial};
    unsigned n, j;
    if (argc != 3 || !a || !b || !ea || !eb || !sd_profile_load(argv[1], &dna) || !sd_profile_load(argv[2], &low)) return 2;
    config = smo_recipe_config(&dna, &low); space.spatial = 1;
    CHECK(smo_render_init(a, ea, &config, &c) && smo_render_init(b, eb, &config, &space), "direct and spatial monitor initialize");
    for (n = 0; n < 10; ++n) {
        CHECK(smo_render_process(a, ao, 1024, 0, &ac) && smo_render_process(b, bo, 1024, 0, &bc), "monitor renders arbitrary host blocks");
        CHECK(!memcmp(ad, bd, sizeof ad) && !memcmp(al, bl, sizeof al), "monitor selection never changes either source");
        for (j = n ? 0 : 480; j < 2048; ++j) {
            CHECK(ao[j] == dry[j], "direct monitor exactly preserves dry float after onset");
            CHECK(bo[j] == spatial[j], "spatial monitor exactly preserves renderer float after onset");
        }
    }
    {
        uint64_t frame = a->scene.frame;
        SmoControl invalid = c; invalid.spatial = 2;
        CHECK(!smo_render_set(a, &invalid) && a->scene.frame == frame && a->target.spatial == 0, "invalid monitor selection is atomic");
        CHECK(!smo_render_process(a, NULL, 1, 1, NULL) && !a->stopping, "invalid output does not latch stop");
        CHECK(smo_render_process(a, NULL, 0, 1, NULL) && !a->stopping, "empty block does not latch stop");
    }
    c.scene.space = space.scene.space = .65;
    c.scene.propagation = space.scene.propagation = 1;
    space.spatial = 0;
    CHECK(smo_render_set(a, &c) && smo_render_set(b, &space), "switch monitor without source reset");
    for (n = 0; n < 60; ++n) {
        smo_render_process(a, ao, 512, 0, &ac); smo_render_process(b, bo, 512, 0, &bc);
        CHECK(!memcmp(ad, bd, 1024 * sizeof(float)), "dry/spatial crossfade preserves raw DNA");
    }
    CHECK(b->spatial_mix == 0 && a->scene.frame == b->scene.frame, "linear crossfade settles and clocks remain aligned");
    CHECK(smo_render_process(a, ao, 1024, 1, NULL), "stop render");
    CHECK(a->release == 480, "stop fade reaches exactly480 samples");
    for (j = 960; j < 2048; ++j) CHECK(ao[j] == 0, "stop output remains exactly zero");
    CHECK(smo_render_init(a, ea, &config, &c), "restart resets envelope");
    CHECK(smo_render_process(a, ao, 1, 0, NULL) && ao[0] == 0 && ao[1] == 0 && a->scene.frame == 1, "restart begins at source frame0 with zero onset");
    config.channels = 12;
    CHECK(!smo_render_init(a, ea, &config, &c), "stereo device adapter rejects multichannel layout");
    free(a); free(b); free(ea); free(eb);
    if (!failures) puts("PASS: dry/spatial preservation, raw-source isolation, switch continuity, empty/invalid calls, stop/restart envelopes");
    return failures ? 1 : 0;
}
