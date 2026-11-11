#include "profile.h"
/* Centres follow the existing V10 engineering formants. Q and delay are
   explicit exploratory values; no measured manifold/acoustic identification. */
static const VslPhaseProfile profiles[]={
    {"base",{260,1250,3100},0,0},
    {"delay",{260,1250,3100},0,.001},
    {"mild",{260,1250,3100},.7,0},
    {"strong",{260,1250,3100},1.4,0}
};
const VslPhaseProfile *vsl_phase_profile(int mode) { return mode>=0&&mode<4?&profiles[mode]:0; }
