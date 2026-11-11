#ifndef VSL_APP_TAKES_H
#define VSL_APP_TAKES_H
#include "audio_device.h"
typedef struct { VslTake take;int saved;wchar_t path[MAX_PATH]; } VslTakes;
void vsl_takes_free(VslTakes *takes);
/* Call with worker joined. Autosave before replacing any unsaved take. */
int vsl_takes_preserve(VslTakes *takes,const wchar_t *workspace);
int vsl_takes_new(VslTakes *takes,VslAudio *audio);
int vsl_takes_save(VslTakes *takes,const wchar_t *path);
int vsl_takes_play(VslTakes *takes,VslAudio *audio,const wchar_t *path);
#endif
