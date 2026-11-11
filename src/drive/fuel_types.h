#ifndef VSL_FUEL_TYPES_H
#define VSL_FUEL_TYPES_H
typedef enum {
    VSL_FUEL_OFF, VSL_FUEL_FIRE, VSL_FUEL_DELAY, VSL_FUEL_CUT, VSL_FUEL_RESUME
} VslFuelMode;
typedef struct {
    VslFuelMode mode;
    double closed_seconds, resume_seconds, command;
} VslFuel;
#endif
