#include "profile.h"
/* Explicit engineering audition values, not an identified pressure trace or
   engine-block FRF. Broad short pressure responses and slower structure are
   kept separate. Existing V011 exhaust coefficients are never replaced. */
static const VslCharacterProfile profile={
    {{1050,.0014,.85},{2900,.00065,.52},{6100,.00032,.24}},
    {{610,.012,.26},{1180,.008,.42},{2240,.005,.60},
     {3870,.0035,.40},{5820,.0025,.22}},
    .035,.240,3.0,.22,.30,.35
};
const VslCharacterProfile *vsl_character_profile(void) { return &profile; }
