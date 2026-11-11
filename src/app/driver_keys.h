#ifndef VSL_DRIVER_KEYS_H
#define VSL_DRIVER_KEYS_H
#include <windows.h>

typedef enum {
    VSL_KEY_NONE, VSL_KEY_CONSUMED,
    VSL_KEY_THROTTLE_DOWN, VSL_KEY_THROTTLE_UP,
    VSL_KEY_BRAKE_DOWN, VSL_KEY_BRAKE_UP,
    VSL_KEY_GEAR_DOWN, VSL_KEY_GEAR_UP
} VslDriverKey;

/* UI routing only: no engine state, device work or simulation integration.
   An armed pedal release remains valid when focus/mode changes. */
VslDriverKey vsl_driver_key(HWND root,const MSG *message,int enabled,
                            int throttle_held,int brake_held);
#endif
