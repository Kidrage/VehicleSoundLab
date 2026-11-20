#include "engine.h"
/* Engineering placeholders, NOT measured Lamborghini/Porsche profiles. */
static const VslProfile profiles[VSL_PROFILE_COUNT] = {
    {"V10 / 5.2 common pin", 10, 850, 8500, {260,1250,3100}, {.65f,.50f,.38f}, 1.02f, .00038f,
      {0,1,0,1,0,1,0,1,0,1}},
    {"V8 / crossplane", 8, 750, 7000, {135,620,1900}, {.70f,.55f,.45f}, 1.28f, .00062f,
      {0,1,0,0,1,0,1,1,0,0}},
    {"Flat-six / turbo", 6, 800, 7200, {220,820,2100}, {.70f,.50f,.42f}, 1.35f, .00045f,
      {0,1,0,1,0,1,0,0,0,0}},
    {"SCI-FI / oscillator DNA", 6, 650, 9000, {150,650,1800}, {.65f,.55f,.50f}, 1.10f, .00030f,
      {0,1,0,1,0,1,0,0,0,0}},
    {"V12 / even fire",12,780,8800,{210,1180,3400},{.65f,.48f,.4f},1.0f,.0003f,
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
    p.load = .18f; p.master = .35f; p.dna = .85f; p.pad = .20f;
    p.noise = .25f; p.brightness = .5f; p.space = .08f;
    p.drive_mode=VSL_BENCH;p.ignition=1;p.start_id=1;p.gear=1;p.auto_gear=1;
    p.width=.55f;p.detail=.55f;p.intake=.4f;p.mechanical=.35f;p.backfire=1;
    p.idle_body=.6f;p.irregularity=.35f;p.release_time=.32f;p.event_level=.5f;
    p.fuel_cut=1;p.pumping=.65f;
    p.mechanical_model=1;
    p.combustion_variation=1;
    p.propagation=0; /* Optional listener experiment; factory timbre stays frozen. */
    p.firing_source=VSL_SOURCE_OSC;p.pulse_amount=1; /* Explicit opt-in; original voice at mode0. */
    p.event_color=0; /* Optional main-pressure control, absent in old presets. */
    p.response_shape=0; /* Optional shape control; missing presets stay off. */
    p.pressure_texture=0;p.structure_transfer=0; /* Opt-in character experiment. */
    return p;
}
