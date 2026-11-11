#ifndef VSL_SCENE_MONITOR_RECIPE_H
#define VSL_SCENE_MONITOR_RECIPE_H
#include "scene_monitor/render.h"
DsSceneConfig smo_recipe_config(const SdProfile *dna, const SdProfile *low);
SmoControl smo_recipe_control(void);
#endif
