#include "voicing.h"
/* State rows: exhaust, body, intake, mechanical, airflow, high-order detail.
   Shared engineering response for the five templates; timbre geometry stays
   in core/profiles.c. Measured per-car maps can replace this data separately. */
static const VslVoicingProfile response = {
    {
        {{1.00f,1.05f,.70f,1.10f,.55f,.65f}, .10f,.70f}, /* idle */
        {{ .94f, .85f,1.10f,1.00f,.85f,.90f}, .01f,1.00f}, /* free rev */
        {{1.05f,1.00f,1.18f, .92f,1.12f,1.12f},-.04f,1.12f}, /* pull */
        {{ .90f, .95f, .72f, .95f,.70f,.75f}, .05f,.88f}, /* cruise */
        {{ .72f,1.06f, .18f,1.00f,.28f,.16f}, .17f,.58f}, /* overrun */
        {{1.00f,1.00f,1.00f,1.00f,1.00f,1.00f}, .07f,.84f}, /* shift cut */
        {{1.00f,1.00f,1.05f,1.00f,1.00f,1.00f},-.01f,1.03f}, /* recovery */
        {{ .98f, .90f,1.12f,1.00f, .90f,1.02f},-.01f,1.03f} /* restrained rev match */
    },
    {.014f,.055f,.012f,.025f,.012f,.010f},
    {.060f,.070f,.030f,.100f,.035f,.025f},
    {1.00f,.28f,1.28f,.18f,1.10f,1.34f},
    {.012f,.040f,.008f,.045f,.010f,.007f},
    {.065f,.140f,.030f,.100f,.045f,.040f},
    {1.10f,1.20f,1.35f,1.05f,1.20f,1.35f},
    {.72f,.10f,.95f,.08f,.55f,.82f}
};
const VslVoicingProfile *vsl_voicing_profile(int profile) { (void)profile;return &response; }
const char *vsl_layer_name(int layer) {
    static const char *names[]={"exhaust","body","intake","mechanical","air","high_orders"};
    return layer>=0&&layer<VSL_LAYERS?names[layer]:"invalid";
}
