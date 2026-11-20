#include "combustion.h"
#include "core/types.h"
/* Engineering pressure variation, not measured COV/ignition timing. The time
   offset warps the acoustic waveform; it NEVER retimes the drivetrain crank. */
static const VslCombustionProfile v10={.18f,.09f,.00012f,.000045f,.25f,.025f};
const VslCombustionProfile *vsl_combustion_profile(int profile) {
    return profile==VSL_V10?&v10:0;
}
