#ifndef VSL_PROPAGATION_H
#define VSL_PROPAGATION_H
#include "propagation_types.h"
/* +y is the listener's left; listener faces vehicle +x. */
void vsl_propagation_init(VslPropagation *state);
void vsl_propagation_target(VslPropagation *state,int object,const VslObjectInfo *position,
    double listener_x,double listener_y,double listener_z,double sample_rate);
void vsl_propagation_begin(VslPropagation *state,int enabled);
void vsl_propagation_tick(VslPropagation *state,int object,double input,double paths[VSL_PATH_COUNT]);
void vsl_propagation_advance(VslPropagation *state);
#endif
