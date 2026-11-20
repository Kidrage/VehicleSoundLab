#include "vehicle.h"
#include <math.h>
/* Shared placeholder for all five voices, not five identified vehicles.
   600 Nm @ 6500 and 470 kW @ 8000 are the Performante brochure anchors.
   Between them, and everywhere else, this is a linear engineering curve.
   The retained ratios are RPM/kph, NOT dimensionless gearbox ratios. */
static const VslVehicleProfile proxy={
    1600,70,.22f,1.225f,.72f,.013f,.90f,1.10f,1.05f,1.35f,
    600,35,55,.97f,
    {114.2f,76.7f,55.5f,43.8f,34.3f,27.7f,22.6f}
};
const VslVehicleProfile *vsl_vehicle_profile(int profile) { (void)profile;return &proxy; }
float vsl_torque_fraction(float x) {
    static const float rpm[]={0,.10f,.25f,.45f,.65f,6500.0f/8500,.88f,8000.0f/8500,1};
    static const float torque[]={.48f,.50f,.65f,.82f,.96f,1,.99f,.9350352904145726f,.89f};
    unsigned i;
    if(x<=rpm[0])return torque[0];
    for(i=1;i<sizeof rpm/sizeof rpm[0];++i)if(x<=rpm[i])
        return fminf(torque[i-1]+(torque[i]-torque[i-1])*(x-rpm[i-1])/(rpm[i]-rpm[i-1]),
            .9350352904145726f*(8000.0f/8500)/x);
    return .9350352904145726f*(8000.0f/8500)/x;
}
