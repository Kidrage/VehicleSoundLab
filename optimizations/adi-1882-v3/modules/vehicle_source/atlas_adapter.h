#ifndef VSL_VEHICLE_SOURCE_ATLAS_ADAPTER_H
#define VSL_VEHICLE_SOURCE_ATLAS_ADAPTER_H
#include "api.h"
#include "atlas_drive/render.h"
/* Non-RT migration boundary for existing owned recipes. The main source API
   deliberately doesn't expose AdConfig, VslEngine, scene or speaker layouts. */
VsAssets *vs_assets_from_atlas(const AdConfig *config);
void vs_control_from_atlas(const AdControl *old,VsControl *control);
#endif
