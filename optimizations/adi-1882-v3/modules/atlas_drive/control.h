#ifndef VSL_ATLAS_DRIVE_CONTROL_H
#define VSL_ATLAS_DRIVE_CONTROL_H
#include "core/types.h"

typedef struct {
    int mode, ignition, start_id, gear, automatic, backfire;
    float rpm, load, throttle, brake;
} AdInput;
typedef struct {
    float gain, detail, event_gain, width, room, perspective;
    int spatial, propagation;
    float residual_gain; /* Independent 0..1 detail layer; default zero. */
    float body_mix; /* 0..1 moves measured LF to the body envelope; default0. */
    float intake_gain, mechanical_gain, air_gain, road_gain, wind_gain; /* Engineering auxiliary layers; default0. */
    float startup_gain; /* Independent observed-stereo startup layer, default0. */
    float catch_gain; /* Optional coherent CATCH LF support, default0. */
    float resonant_gain; /* Optional local continuous resonance detail, default0. */
    float coherent_low_gain; /* Independent measured-phase LF recipe, default0. */
    float idle_mix; /* Optional typed fixed-idle source replacement0..1, default0. */
    float idle_motion,idle_detail; /* Optional fine-idle core motion/detail amount,0..1. */
} AdMix;
typedef struct { AdInput drive; AdMix mix; } AdControl;

int ad_control_valid(const AdControl *control, int channels);
/* Apply only host inputs. Integration time, gear, RPM and event latches remain
   exclusively owned by the existing200Hz driving controller. */
void ad_control_apply(VslEngine *storage, const AdControl *control);
#endif
