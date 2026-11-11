#include "engine.h"
/* Engineering placeholders, NOT measured Lamborghini/Porsche profiles. */
static const VslProfile profiles[VSL_PROFILE_COUNT] = {
    {"V10 / 5.2 common pin", 10, 850, 8500, {260,1250,3100}, {.65,.50,.38}, 1.02, .00038,
      {0,1,0,1,0,1,0,1,0,1}},
    {"V8 / crossplane", 8, 750, 7000, {135,620,1900}, {.70,.55,.45}, 1.28, .00062,
      {0,1,0,0,1,0,1,1,0,0}},
    {"Flat-six / turbo", 6, 800, 7200, {220,820,2100}, {.70,.50,.42}, 1.35, .00045,
      {0,1,0,1,0,1,0,0,0,0}},
    {"SCI-FI / oscillator DNA", 6, 650, 9000, {150,650,1800}, {.65,.55,.50}, 1.10, .00030,
      {0,1,0,1,0,1,0,0,0,0}},
    {"V12 / even fire",12,780,8800,{210,1180,3400},{.65,.48,.4},1.0,.0003,
      {0,1,0,1,0,1,0,1,0,1,0,1}}
};
const VslProfile *vsl_profile(int id) {
    if (id < 0 || id >= VSL_PROFILE_COUNT) id = 0;
    return &profiles[id];
}
VslParams vsl_default_params(int id) {
    VslParams p = {0};
    p.profile = (id >= 0 && id < VSL_PROFILE_COUNT) ? id : 0;
    p.rpm = vsl_profile(p.profile)->idle_rpm;
    p.load = .18; p.master = .35; p.dna = .85; p.pad = .20;
    p.noise = .25; p.brightness = .5; p.space = .08;
    p.drive_mode=VSL_BENCH;p.ignition=1;p.start_id=1;p.gear=1;p.auto_gear=1;
    p.width=.55;p.detail=.55;p.intake=.4;p.mechanical=.35;p.backfire=1;
    p.idle_body=.6;p.irregularity=.35;p.release_time=.32;p.event_level=.5;
    p.fuel_cut=1;p.pumping=.65;
    p.mechanical_model=1;
    p.combustion_variation=1;
    p.propagation=0; /* Optional listener experiment; factory timbre stays frozen. */
    p.firing_source=VSL_SOURCE_OSC;p.pulse_amount=1; /* Explicit opt-in; original voice at mode0. */
    p.event_color=0; /* Optional main-pressure control, absent in old presets. */
    p.response_shape=0; /* Optional shape control; missing presets stay off. */
    p.pressure_texture=0;p.structure_transfer=0; /* Opt-in character experiment. */
    return p;
}
