#ifndef VSL_SESSION_PARAMETERS_H
#define VSL_SESSION_PARAMETERS_H
#include <stddef.h>
#include "core/types.h"
/* Protocol order is explicit; new fields require a new take schema. */
#define VSL_TAKE_FIELDS(I,D) \
 I(profile) I(pure_osc) D(rpm) D(load) D(master) D(dna) D(pad) D(noise) D(brightness) D(space) \
 I(drive_mode) I(ignition) I(start_id) I(gear) I(auto_gear) I(backfire) \
 D(throttle) D(brake) D(width) D(perspective) D(detail) D(intake) D(mechanical) \
 D(idle_body) D(irregularity) D(release_time) D(event_level) I(fuel_cut) \
 D(pumping) I(mechanical_model) I(combustion_variation) I(propagation) \
 D(pressure_texture) D(structure_transfer) D(response_shape) D(event_color) I(firing_source) D(pulse_amount)
typedef struct { const char *name;size_t offset;int integer; } VslParamField;
const VslParamField *vsl_take_fields(unsigned *count);
int vsl_params_same(const VslParams *a,const VslParams *b);
int vsl_take_params_valid(const VslParams *p);
#endif
