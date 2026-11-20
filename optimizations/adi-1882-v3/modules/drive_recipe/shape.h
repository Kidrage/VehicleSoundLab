#ifndef VSL_DRIVE_RECIPE_SHAPE_H
#define VSL_DRIVE_RECIPE_SHAPE_H
#include "bank.h"
#include "drive_resonance/voice.h"
float drc_support(const DrcBank *bank,unsigned anchor,float root_hz);
void drc_weights(const DrcBank *bank,float root_hz,float weights[SA_MAX_ANCHORS]);
/* Predict the SAME post-follow root/detail amount used by the next main sample.
   Power withdrawal follows detail amplitude squared and local support squared. */
int drc_shape(const DrcBank *bank,const SaVoice *dna,const DrsVoice *detail,
              float gain[SD_MAX_HARMONICS]);
#endif
