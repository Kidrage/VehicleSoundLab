#ifndef VSL_DENSE_MODEL_H
#define VSL_DENSE_MODEL_H
#include <stdint.h>
typedef struct { unsigned bin; double real,imag; } DoTone;
typedef struct { int start; unsigned count; DoTone *tones; } DoGrain;
typedef struct { unsigned rate,frames,window,hop,count; DoGrain *grains; } DoModel;
int do_model_load(const char *path,DoModel *model);
void do_model_free(DoModel *model);
#endif
