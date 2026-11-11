#include "routing.h"
#include <string.h>

int ds_routing_valid(DsProjection p, DsRoute r) {
    return p >= DS_OBSERVE_LEFT && p <= DS_OBSERVE_MID && r >= DS_ROUTE_PAIR && r <= DS_ROUTE_RIGHT;
}

void ds_route_frame(const DsSourceFrame *s, DsProjection p, DsRoute r, VslObjectFrame *o) {
    double l = s->dna[0] + s->low[0], right = s->dna[1] + s->low[1];
    double mono = p == DS_OBSERVE_LEFT ? l : p == DS_OBSERVE_RIGHT ? right : .5 * (l + right);
    memset(o, 0, sizeof *o);
    if (r == DS_ROUTE_PAIR) o->sample[VSL_EXHAUST_L] = o->sample[VSL_EXHAUST_R] = .5 * mono;
    else o->sample[r == DS_ROUTE_LEFT ? VSL_EXHAUST_L : VSL_EXHAUST_R] = mono;
}
