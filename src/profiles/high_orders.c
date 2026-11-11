#include "high_orders.h"
#include "core/types.h"
/* V10 review candidate, not measured Lamborghini coefficients. Density
   compensation avoids an arbitrary RMS increase at lower bank frequencies. */
static const VslHighOrderProfile v10={3900,.78,.0035,50,14000,48,.55};
const VslHighOrderProfile *vsl_high_order_profile(int profile) {
    return profile==VSL_V10?&v10:0;
}
