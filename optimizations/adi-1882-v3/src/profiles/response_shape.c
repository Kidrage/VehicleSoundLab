#include "profiles/response_shape.h"
#include <math.h>
/* Deliberate response-shape controls, not measured Lamborghini damping.
   Centre is the existing recipe; endpoints retain all modal frequencies. */
static const VslResponseProfile profile={{.55f,1,1.7f},.55f,.20f,.25f,1200,8000};
const VslResponseProfile *vsl_response_profile(void) { return &profile; }
static float unit(float x) { return fmaxf(0,fminf(1,x)); }
float vsl_response_coordinate(float rpm,float pull,float shape,float amount) {
    const VslResponseProfile *p=&profile;
    float speed=unit((rpm-p->rpm_low)/(p->rpm_high-p->rpm_low));
    return unit(amount)*(p->load_weight*(2*unit(pull)-1)+p->rpm_weight*(2*speed-1)+p->event_weight*fmaxf(-1,fminf(1,shape)));
}
