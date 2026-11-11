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
} AdMix;
typedef struct { AdInput drive; AdMix mix; } AdControl;

int ad_control_valid(const AdControl *control, int channels);
/* Apply only host inputs. Integration time, gear, RPM and event latches remain
   exclusively owned by the existing200Hz driving controller. */
void ad_control_apply(VslEngine *storage, const AdControl *control);
#endif
