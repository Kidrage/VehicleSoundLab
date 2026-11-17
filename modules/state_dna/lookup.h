#ifndef VSL_STATE_DNA_LOOKUP_H
#define VSL_STATE_DNA_LOOKUP_H
#include "api.h"
void sx_position(const SaBank *bank,double root,unsigned *lo,unsigned *hi,double *blend);
double sx_phase(const SaBank *bank,double root,unsigned harmonic,unsigned channel);
double sx_magnitude(const SaBank *bank,const SdTexture *texture,double detail,
                    unsigned lo,unsigned hi,double blend,unsigned harmonic,unsigned channel);
#endif
