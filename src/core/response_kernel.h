#ifndef VSL_RESPONSE_KERNEL_H
#define VSL_RESPONSE_KERNEL_H
#include "core/modal.h"
#include "profiles/character.h"
#define VSL_RESPONSE_MAX_MODES VSL_CHARACTER_STRUCTURE_MODES
typedef struct {
    VslMode mode[3][VSL_RESPONSE_MAX_MODES];
    double gram[3][3][VSL_RESPONSE_MAX_MODES][VSL_RESPONSE_MAX_MODES];
    unsigned count;
} VslResponseKernel;
void vsl_response_kernel_init(VslResponseKernel *k,const VslCharacterMode *modes,unsigned count,double rate);
void vsl_response_kernel_advance(VslResponseKernel *k);
void vsl_response_kernel_strike(VslResponseKernel *k,const double *weights,double gain,double coordinate,double elapsed);
double vsl_response_kernel_read(const VslResponseKernel *k);
#endif
