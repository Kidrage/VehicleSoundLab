#ifndef VSL_ATLAS_DRIVE_CONTROL_H
#define VSL_ATLAS_DRIVE_CONTROL_H
#include "core/types.h"

typedef struct {
    int mode, ignition, start_id, gear, automatic, backfire;
    double rpm, load, throttle, brake;
} AdInput;
typedef struct {
    double gain, detail, event_gain, width, room, perspective;
    int spatial, propagation;
    double residual_gain; /* Independent 0..1 detail layer; default zero. */
    double body_mix; /* 0..1 moves measured LF to the body envelope; default0. */
    double intake_gain, mechanical_gain, air_gain, road_gain, wind_gain; /* Engineering auxiliary layers; default0. */
    double startup_gain; /* Independent observed-stereo startup layer, default0. */
} AdMix;
typedef struct { AdInput drive; AdMix mix; } AdControl;

int ad_control_valid(const AdControl *control, int channels);
/* Apply only host inputs. Integration time, gear, RPM and event latches remain
   exclusively owned by the existing200Hz driving controller. */
void ad_control_apply(VslEngine *storage, const AdControl *control);
#endif
