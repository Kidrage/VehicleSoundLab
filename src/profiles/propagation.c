#include "propagation.h"
static const VslPropagationProfile profile={343,.18,1.4,.35,.018,1800,.65};
const VslPropagationProfile *vsl_propagation_profile(void) { return &profile; }
