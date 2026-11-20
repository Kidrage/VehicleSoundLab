#include "profiles/character.h"
/* Explicit engineering audition values, not an identified pressure trace or
   engine-block FRF. Broad short pressure responses and slower structure are
   kept separate. Existing V011 exhaust coefficients are never replaced. */
static const VslCharacterProfile profile={
    {{1050,.0014f,.85f},{2900,.00065f,.52f},{6100,.00032f,.24f}},
    {{610,.012f,.26f},{1180,.008f,.42f},{2240,.005f,.60f},
     {3870,.0035f,.40f},{5820,.0025f,.22f}},
    .035f,.240f,3.0f,.22f,.30f,.35f
};
const VslCharacterProfile *vsl_character_profile(void) { return &profile; }
