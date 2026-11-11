#ifndef VSL_DRIVE_AUX_VOICE_H
#define VSL_DRIVE_AUX_VOICE_H
#include "core/types.h"
enum { DA_INTAKE,DA_MECHANICAL,DA_AIR,DA_ROAD,DA_WIND,DA_LAYERS };
typedef struct { double amount[DA_LAYERS],target[DA_LAYERS],follow; } DaVoice;
/* Owner is exclusive to atlas_drive. Reuses its independently seeded modal/NVH
   storage, not old DNA/PAD/exhaust. Engineering templates, not measured source
   separation. All generators advance even with amounts zero. */
int da_voice_init(DaVoice *voice,VslEngine *owner,const double amounts[DA_LAYERS]);
int da_voice_set(DaVoice *voice,const double amounts[DA_LAYERS]);
void da_voice_tick(DaVoice *voice,VslEngine *owner,VslObjectFrame *raw,VslObjectFrame *mixed);
/* Direct electrical monitor: mono sources at equal-power centre, air L/R direct.
   Spatial routing is performed once later from the same mixed source objects. */
void da_stereo(const VslObjectFrame *mixed,double stereo[2]);
#endif
