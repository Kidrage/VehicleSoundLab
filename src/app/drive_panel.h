#ifndef VSL_DRIVE_PANEL_H
#define VSL_DRIVE_PANEL_H
#include <windows.h>
#include "core/types.h"
enum { ID_IGNITION=400,ID_START,ID_GEAR_DOWN,ID_NEUTRAL,ID_GEAR_UP,ID_AUTOGEAR,ID_BACKFIRE };
void vsl_drive_panel_create(HWND parent,HFONT font,int y);
void vsl_drive_panel_sync(const VslParams *params);
int vsl_drive_panel_command(int id,VslParams *params,int current_gear);
#endif
