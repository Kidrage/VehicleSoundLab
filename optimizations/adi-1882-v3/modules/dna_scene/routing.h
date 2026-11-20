#ifndef VSL_DNA_SCENE_ROUTING_H
#define VSL_DNA_SCENE_ROUTING_H
#include "source.h"
#include "spatial/objects.h"

typedef enum { DS_OBSERVE_LEFT, DS_OBSERVE_RIGHT, DS_OBSERVE_MID } DsProjection;
typedef enum { DS_ROUTE_PAIR, DS_ROUTE_LEFT, DS_ROUTE_RIGHT } DsRoute;
int ds_routing_valid(DsProjection projection, DsRoute route);
/* Explicit mono projection of a mixed recording model, not bank separation.
   Paired outlets receive half amplitude each; their coherent sum is preserved. */
void ds_route_frame(const DsSourceFrame *source, DsProjection projection, DsRoute route, VslObjectFrame *objects);
#endif
