#ifndef VSL_STATE_DNA_LOOKUP_H
#define VSL_STATE_DNA_LOOKUP_H
#include "api.h"
void sx_position(const SaBank *bank,float root,unsigned *lo,unsigned *hi,float *blend);
float sx_phase(const SaBank *bank,float root,unsigned harmonic,unsigned channel);
float sx_magnitude(const SaBank *bank,const SdTexture *texture,float detail,
                    unsigned lo,unsigned hi,float blend,unsigned harmonic,unsigned channel);
#endif
