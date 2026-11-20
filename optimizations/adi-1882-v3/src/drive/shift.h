#ifndef VSL_SHIFT_H
#define VSL_SHIFT_H
#include "types.h"
void vsl_shift_cancel(VslDrive *drive);
int vsl_shift_request(VslDrive *drive,int next,float max_rpm);
void vsl_shift_step(VslDrive *drive,float idle_rpm,float max_rpm,float dt);
const char *vsl_shift_stage_name(VslShiftStage stage);
#endif
