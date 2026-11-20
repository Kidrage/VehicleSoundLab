#ifndef VSL_EVENT_COLOR_H
#define VSL_EVENT_COLOR_H
#include "engine.h"
int vsl_color_init(VslEventColor *s,float rate,float amount);
void vsl_color_tick(VslEventColor *s,const VslEngine *e,VslObjectFrame *o,const float main_pressure[2]);
#endif
