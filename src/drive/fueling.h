#ifndef VSL_FUELING_H
#define VSL_FUELING_H
#include "core/types.h"
void vsl_fueling_step(VslDrive *drive,const VslParams *params,double dt);
/* Permission for a NEW fired acoustic event, separate from response ringdown. */
int vsl_fueling_allows_firing(const VslDrive *drive);
const char *vsl_fuel_mode_name(VslFuelMode mode);
#endif
