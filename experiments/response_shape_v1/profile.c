#include "profile.h"
#include <math.h>
/* Deliberate response-shape controls, not measured Lamborghini damping.
   Centre is the existing recipe; endpoints retain all modal frequencies. */
static const VslResponseProfile profile={{.55,1,1.7},.55,.20,.25,1200,8000};
const VslResponseProfile *vsl_response_profile(void) { return &profile; }
static double unit(double x) { return fmax(0,fmin(1,x)); }
double vsl_response_coordinate(double rpm,double pull,double shape,double amount) {
    const VslResponseProfile *p=&profile;
    double speed=unit((rpm-p->rpm_low)/(p->rpm_high-p->rpm_low));
    return unit(amount)*(p->load_weight*(2*unit(pull)-1)+p->rpm_weight*(2*speed-1)+p->event_weight*fmax(-1,fmin(1,shape)));
}
