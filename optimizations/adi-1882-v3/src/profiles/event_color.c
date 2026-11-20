#include "profiles/event_color.h"
/* Exploratory main-pressure coloration, not identified exhaust parameters. */
static const VslEventColorProfile p={{1400,4500},.0015f,.45f,.90f,.35f};
const VslEventColorProfile *vsl_event_color_profile(void) { return &p; }
