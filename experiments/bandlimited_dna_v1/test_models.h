#ifndef VSL_BANDLIMITED_TEST_MODELS_H
#define VSL_BANDLIMITED_TEST_MODELS_H
#include "sound_dna/profile.h"
#define BD_PI 3.14159265358979323846
#define CHECK(x) do { if(!(x)) { fprintf(stderr,"bandlimited check line%d: %s\n",__LINE__,#x);return 1; } } while(0)
/* Synthetic engineering fixtures, never recorded source/RPM observations. */
void bd_model(SdProfile *model,double root,unsigned harmonics,int texture);
#endif
