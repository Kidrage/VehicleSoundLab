#ifndef VSL_EVENT_COLOR_H
#define VSL_EVENT_COLOR_H
#include "engine.h"
int vsl_color_init(VslEventColor *s,double rate,double amount);
void vsl_color_tick(VslEventColor *s,const VslEngine *e,VslObjectFrame *o,const double main_pressure[2]);
#endif
