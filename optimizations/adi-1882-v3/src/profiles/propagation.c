#include "propagation.h"
static const VslPropagationProfile profile={343,.18f,1.4f,.35f,.018f,1800,.65f};
const VslPropagationProfile *vsl_propagation_profile(void) { return &profile; }
