#ifndef VSL_DRIVE_RECIPE_SHAPE_H
#define VSL_DRIVE_RECIPE_SHAPE_H
#include "bank.h"
#include "drive_resonance/voice.h"
double drc_support(const DrcBank *bank,unsigned anchor,double root_hz);
void drc_weights(const DrcBank *bank,double root_hz,double weights[SA_MAX_ANCHORS]);
/* Predict the SAME post-follow root/detail amount used by the next main sample.
   Power withdrawal follows detail amplitude squared and local support squared. */
int drc_shape(const DrcBank *bank,const SaVoice *dna,const DrsVoice *detail,
              double gain[SD_MAX_HARMONICS]);
#endif
