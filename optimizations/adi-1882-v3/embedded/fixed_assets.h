#ifndef VSL_FIXED_ASSETS_H
#define VSL_FIXED_ASSETS_H
#include "vehicle_source/atlas_adapter.h"
/* Fixed production bank. Its immutable coefficients remain resident and are
   counted in the linked image; no startup loader arena is retained. */
VsAssets *vsl_fixed_assets_acquire(void);
void vsl_fixed_assets_release(VsAssets *assets);
AdControl vsl_fixed_initial(void);
#endif
