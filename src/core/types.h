#ifndef VSL_TYPES_H
#define VSL_TYPES_H
#include <stdint.h>
#include "drive/types.h"
#include "voice_types.h"
#include "spatial/types.h"
#include "events.h"
#include "high_order_types.h"
#include "excitation_types.h"
#include "mechanical_types.h"
#include "combustion_types.h"
#include "character_types.h"
#include "response_types.h"
#include "event_color_types.h"
#include "firing_source_types.h"
#define VSL_VERSION "0.20.0"
#define VSL_WIDEN_INNER(x) L##x
#define VSL_WIDEN(x) VSL_WIDEN_INNER(x)
#define VSL_VERSION_W VSL_WIDEN(VSL_VERSION)
#define VSL_PARTIALS 128
#define VSL_MAX_IR 8192
#define VSL_PI 3.14159265358979323846
typedef enum { VSL_V10, VSL_V8, VSL_FLAT6, VSL_SCIFI, VSL_V12, VSL_PROFILE_COUNT } VslProfileId;
typedef struct {
    const char *name;
    int cylinders;
    double idle_rpm, max_rpm;
    double formant[3], formant_width[3], tilt, bank_delay;
    int bank[12];
} VslProfile;
typedef struct {
    int profile, pure_osc;
    double rpm, load, master, dna, pad, noise, brightness, space;
    int drive_mode, ignition, start_id, gear, auto_gear, backfire;
    double throttle, brake, width, perspective, detail, intake, mechanical;
    double idle_body, irregularity, release_time, event_level;
    int fuel_cut;
    int mechanical_model;
    int combustion_variation;
    int propagation;
    double pumping;
    double pressure_texture,structure_transfer,response_shape,event_color;
    int firing_source;
    double pulse_amount;
} VslParams;
typedef struct {
    double rpm, load, phase, throttle_delta;
    double throttle, acceleration;
} VslControl;
typedef struct {
    double real[VSL_PARTIALS], imag[VSL_PARTIALS];
    double target_real[VSL_PARTIALS], target_imag[VSL_PARTIALS];
    double right_real[VSL_PARTIALS], right_imag[VSL_PARTIALS];
    double target_right_real[VSL_PARTIALS], target_right_imag[VSL_PARTIALS];
    double custom_amp[VSL_PARTIALS], custom_phase[VSL_PARTIALS];
    double custom_root, pitch_phase, factory_scale;
    int custom_count;
} VslDna;
typedef struct { double phase[3]; } VslPad;
typedef struct { uint32_t seed; double low[2], mid[2], high[2], env; } VslNvh;
typedef struct { double metal[2],variation_phase; } VslDetail;
typedef struct {
    double previous_input[2], previous_output[2];
    float history[VSL_MAX_IR], ir[VSL_MAX_IR];
    unsigned cursor, ir_length;
    unsigned tap_count, taps[VSL_MAX_IR];
} VslAcoustics;
typedef struct {
    double sample_rate;
    uint64_t frame;
    VslParams target, smooth;
    VslControl control;
    VslDna dna;
    VslPad pad;
    VslNvh nvh;
    VslAcoustics acoustics;
    VslDrive drive;
    VslVoicing voice;
    VslEvents events;
    VslSpatial spatial;
    VslDetail detail;
    VslHighOrders high_orders;
    VslExcitation excitation;
    VslMechanical mechanical;
    VslCombustion combustion;
    VslCharacter character;
    VslResponseShape response;
    VslEventColor color;
    VslFiringSource firing_source;
    VslObjectFrame objects;
    unsigned control_period;
    double fade, peak;
} VslEngine;
#endif
