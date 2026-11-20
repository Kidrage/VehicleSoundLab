#ifndef VSL_VEHICLE_INPUT_TYPES_H
#define VSL_VEHICLE_INPUT_TYPES_H
#include <stdint.h>
enum {VI_INTERNAL,VI_EXTERNAL};
enum {VI_SPEED=1,VI_ACCELERATION=2,VI_SLIP=4};
typedef struct {
    int source;
    unsigned valid;
    uint64_t sequence;
    float speed_mps,acceleration_mps2,tire_slip;
} ViInput;
typedef struct {ViInput value;uint64_t accepted_frame;int seen;} ViState;
typedef struct {ViInput value;int stale;} ViAdopted;
int vi_valid(const ViInput *input);
/* A new sequence refreshes age. Repeated packets cannot keep stale data alive.
   A source change starts a new sequence domain. No allocation or wall clock. */
int vi_accept(ViState *state,const ViInput *input,uint64_t audio_frame);
ViAdopted vi_at(const ViState *state,uint64_t audio_frame,uint64_t max_age);
#endif
