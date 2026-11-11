#include "checks.h"
static SdProfile dna, low;
int failures;

DsSceneConfig test_config(const SdProfile *d, const SdProfile *l) {
    DsSceneConfig c = {{0}, DS_OBSERVE_LEFT, DS_ROUTE_PAIR, 2};
    c.source.dna = d; c.source.low = l;
    /* Separate RNG storage, explicitly retaining the accepted pair's seeds. */
    c.source.dna_seed = c.source.low_seed = 48271;
    c.source.low_scale = 1.6658265329883064;
    return c;
}

DsSceneControl test_control(void) {
    DsSceneControl c = {{1, 1, 1, 1, 1}, .5, 1, 0, 0, 0};
    return c;
}

int main(int argc, char **argv) {
    if (argc != 3 || !sd_profile_load(argv[1], &dna) || !sd_profile_load(argv[2], &low)) return 2;
    source_checks(&dna, &low);
    spatial_checks(&dna, &low);
    if (!failures) puts("PASS: source equivalence, phase clocks, gains, routing, block invariance, spatial isolation, mirror/mono, height policy, validation");
    return failures ? 1 : 0;
}
