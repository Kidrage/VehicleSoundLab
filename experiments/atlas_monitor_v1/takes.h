#ifndef VSL_ATLAS_UI_TAKES_H
#define VSL_ATLAS_UI_TAKES_H
#include "audio.h"
/* UI/non-RT only; protect an unsaved recording before replacing/closing. */
int am_take_preserve(HWND owner,AmAudio *audio);
int am_take_record(HWND owner,AmAudio *audio,int muted);
int am_take_save_dialog(HWND owner,AmAudio *audio);
int am_take_load_dialog(HWND owner,AmAudio *audio,int muted);
#endif
