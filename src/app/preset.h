#ifndef VSL_PRESET_H
#define VSL_PRESET_H
#include <windows.h>
#include "core/types.h"
void vsl_preset_save(const wchar_t *file,const VslParams *params,const wchar_t *dna,const wchar_t *ir);
int vsl_preset_load(const wchar_t *file,VslParams *params,wchar_t *dna,wchar_t *ir);
#endif
