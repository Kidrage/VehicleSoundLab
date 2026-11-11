#include "profile.h"
/* Exploratory main-pressure coloration, not identified exhaust parameters. */
static const VslEventColorProfile p={{1400,4500},.0015,.45,.90,.35};
const VslEventColorProfile *vsl_event_color_profile(void) { return &p; }
