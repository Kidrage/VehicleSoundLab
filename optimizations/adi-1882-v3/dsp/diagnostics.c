#include "diagnostics.h"
#include <string.h>
#ifdef VSL_CAPTURE_MODULES
unsigned vsl_diag_index;
static float samples[1024][10][2];
void vsl_diag_put(unsigned module,const float x[2]){samples[vsl_diag_index][module][0]=x[0];samples[vsl_diag_index][module][1]=x[1];}
void vsl_diag_copy(float *out,unsigned frames){memcpy(out,samples,frames*20*sizeof(float));}
#endif
