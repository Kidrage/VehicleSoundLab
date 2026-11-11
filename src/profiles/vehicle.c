#include "vehicle.h"
#include <math.h>
/* Shared placeholder for all five voices, not five identified vehicles.
   600 Nm @ 6500 and 470 kW @ 8000 are the Performante brochure anchors.
   Between them, and everywhere else, this is a linear engineering curve.
   The retained ratios are RPM/kph, NOT dimensionless gearbox ratios. */
static const VslVehicleProfile proxy={
    1600,70,.22,1.225,.72,.013,.90,1.10,1.05,1.35,
    600,35,55,.97,
    {114.2,76.7,55.5,43.8,34.3,27.7,22.6}
};
const VslVehicleProfile *vsl_vehicle_profile(int profile) { (void)profile;return &proxy; }
double vsl_torque_fraction(double x) {
    static const double rpm[]={0,.10,.25,.45,.65,6500.0/8500,.88,8000.0/8500,1};
    static const double torque[]={.48,.50,.65,.82,.96,1,.99,.9350352904145726,.89};
    unsigned i;
    if(x<=rpm[0])return torque[0];
    for(i=1;i<sizeof rpm/sizeof rpm[0];++i)if(x<=rpm[i])
        return fmin(torque[i-1]+(torque[i]-torque[i-1])*(x-rpm[i-1])/(rpm[i]-rpm[i-1]),
            .9350352904145726*(8000.0/8500)/x);
    return .9350352904145726*(8000.0/8500)/x;
}
