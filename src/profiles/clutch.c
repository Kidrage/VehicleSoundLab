#include "clutch.h"
static const VslClutchProfile proxy={900,.030,2600,1.2,20,.22,160,400,35,180};
const VslClutchProfile *vsl_clutch_profile(int profile) { (void)profile;return &proxy; }
