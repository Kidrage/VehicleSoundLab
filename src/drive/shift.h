#ifndef VSL_SHIFT_H
#define VSL_SHIFT_H
#include "types.h"
void vsl_shift_cancel(VslDrive *drive);
int vsl_shift_request(VslDrive *drive,int next,double max_rpm);
void vsl_shift_step(VslDrive *drive,double idle_rpm,double max_rpm,double dt);
const char *vsl_shift_stage_name(VslShiftStage stage);
#endif
