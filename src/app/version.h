#ifndef VSL_APP_VERSION_H
#define VSL_APP_VERSION_H
#include "core/types.h"
#ifndef VSL_APP_VERSION
#error Build the application with its explicit application version.
#endif
#define VSL_APP_VERSION_W VSL_WIDEN(VSL_APP_VERSION)
#define VSL_DIAGNOSTIC_FOLDER_W L"app" VSL_APP_VERSION_W
#endif
