#ifndef VSL_OBJECTS_H
#define VSL_OBJECTS_H
#define VSL_OBJECTS 10
#define VSL_MAX_CHANNELS 12
typedef enum { VSL_EXHAUST_L,VSL_EXHAUST_R,VSL_INTAKE,VSL_BODY,VSL_MECHANICAL,
    VSL_AIR_L,VSL_AIR_R,VSL_EVENT,VSL_ROAD,VSL_WIND } VslObjectId;
typedef struct { double sample[VSL_OBJECTS]; } VslObjectFrame;
typedef struct { const char *name; double x,y,z; } VslObjectInfo;
#endif
