#ifndef VSL_FAST_IDLE_MONITOR_H
#define VSL_FAST_IDLE_MONITOR_H
#include "modal_source/profile.h"
#include "modal_texture/profile.h"
#include "spectral_texture/profile.h"
#include <stdint.h>
typedef struct {MsProfile core;MtProfile motion;SfProfile fine;} FmModels;
typedef struct FmRender FmRender;
/* NonRT IO/allocation, explicit model directory, all source files immutable. */
int fm_models_load(FmModels *models,const char *directory);
FmRender *fm_render_create(const FmModels *models,uint64_t seed,double grain);
void fm_render_destroy(FmRender *render);
/* RT source remains at native fixed pitch. Level controls finite18ms ramps;
   grain uses the generic spectral_motion ramp. All sources always advance. */
int fm_render_tick(FmRender *render,double main,double detail,double grain,double level,float stereo[2]);
/* Declared sample-located exercise for device/offline parity, not driving. */
void fm_check_controls(uint64_t frame,double *main,double *detail,double *grain,double *level);
#endif
