#include "recipe.h"

DsSceneConfig smo_recipe_config(const SdProfile *dna, const SdProfile *low) {
    DsSceneConfig c = {{0}, DS_OBSERVE_LEFT, DS_ROUTE_PAIR, 2};
    c.source.dna = dna; c.source.low = low;
    c.source.dna_seed = c.source.low_seed = 48271;
    c.source.low_scale = 1.6658265329883064;
    c.source.phase_seed = 8121907;
    return c;
}

SmoControl smo_recipe_control(void) {
    SmoControl c = {{{1, 1, 1, 1, 1}, .5, 1, 0, 0, 0}, 0};
    return c;
}
