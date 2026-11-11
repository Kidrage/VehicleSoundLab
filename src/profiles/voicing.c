#include "voicing.h"
/* State rows: exhaust, body, intake, mechanical, airflow, high-order detail.
   Shared engineering response for the five templates; timbre geometry stays
   in core/profiles.c. Measured per-car maps can replace this data separately. */
static const VslVoicingProfile response = {
    {
        {{1.00,1.05,.70,1.10,.55,.65}, .10,.70}, /* idle */
        {{ .94, .85,1.10,1.00,.85,.90}, .01,1.00}, /* free rev */
        {{1.05,1.00,1.18, .92,1.12,1.12},-.04,1.12}, /* pull */
        {{ .90, .95, .72, .95,.70,.75}, .05,.88}, /* cruise */
        {{ .72,1.06, .18,1.00,.28,.16}, .17,.58}, /* overrun */
        {{1.00,1.00,1.00,1.00,1.00,1.00}, .07,.84}, /* shift cut */
        {{1.00,1.00,1.05,1.00,1.00,1.00},-.01,1.03}, /* recovery */
        {{ .98, .90,1.12,1.00, .90,1.02},-.01,1.03} /* restrained rev match */
    },
    {.014,.055,.012,.025,.012,.010},
    {.060,.070,.030,.100,.035,.025},
    {1.00,.28,1.28,.18,1.10,1.34},
    {.012,.040,.008,.045,.010,.007},
    {.065,.140,.030,.100,.045,.040},
    {1.10,1.20,1.35,1.05,1.20,1.35},
    {.72,.10,.95,.08,.55,.82}
};
const VslVoicingProfile *vsl_voicing_profile(int profile) { (void)profile;return &response; }
const char *vsl_layer_name(int layer) {
    static const char *names[]={"exhaust","body","intake","mechanical","air","high_orders"};
    return layer>=0&&layer<VSL_LAYERS?names[layer]:"invalid";
}
