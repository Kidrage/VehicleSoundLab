#ifndef VSL_SCENE_H
#define VSL_SCENE_H
#include "core/types.h"
const VslObjectInfo *vsl_object_info(int object);
const char *vsl_channel_name(int channels,int channel);
void vsl_listener_position(double perspective,double *x,double *y,double *z);
void vsl_scene_update(VslEngine *engine,int channels);
void vsl_scene_tick(VslEngine *engine,const VslObjectFrame *objects,double *output,int channels);
#endif
