#include "dsp/perf.h"
#include "internal.h"
#include "atlas_drive/source_process.h"
#include <stdlib.h>
#include "dsp_support/storage.h"
#include <string.h>
#include <math.h>
VSL_STORAGE(vs_engines,VsEngine,1,VSL_DDR)
#ifdef VSL_DSP_STATIC
/* Lifetime follows the single DSP engine slot; no extra runtime allocation. */
VSL_SECTION(VSL_L1_STATE)
static SaSampleCache vs_sample_cache;
#ifdef VSL_ADSP_21569
#pragma align 8
#endif
VSL_SECTION(VSL_L2_HISTORY)
static SaTable vs_table;
#if defined(VSL_DSP_FIR_TAPS) && VSL_DSP_FIR_TAPS <= 512
/* EE-412: place the frequently accessed controller/mechanical state in L2.
   The original embedded owner remains the fallback for other builds. */
VSL_SECTION(VSL_L2_HISTORY)
static VslEngine vs_runtime_owner;
VSL_SECTION(VSL_L2_HISTORY)
static EsPool vs_runtime_events;
#endif
#endif
VsEngine *vs_engine_create(const VsAssets *assets,const VsControl *control) {
    VsEngine *s;AdControl adopted;AdConfig config;
    VslEngine *owner;
    if(!assets||!control||!vi_valid(&control->input)||!ec_control_valid(&control->events)||
       (control->dna_unified!=0&&control->dna_unified!=1)||!dch_control_valid(&control->dna)||
       (control->dna_unified&&(control->intake_gain!=0||control->air_gain!=0||control->road_gain!=0||control->wind_gain!=0)))return NULL;
    vs_control_to_atlas(control,&adopted);
    if(!ad_control_supported(&assets->owned.config,&adopted))return NULL;
    s=vs_engines_acquire();if(!s)return NULL;
    s->event_runtime=&s->event_pool;
#if defined(VSL_DSP_STATIC) && defined(VSL_DSP_FIR_TAPS) && VSL_DSP_FIR_TAPS <= 512
    s->event_runtime=&vs_runtime_events;
#endif
    s->assets=assets;s->adopted=adopted;
    config=assets->owned.config;s->dna_unified=control->dna_unified;
    if(s->dna_unified){
        s->character=dch_create(config.fine_idle_profile,config.seed,&control->dna);
        if(!s->character){vs_engines_release(s);return NULL;}
        config.fine_idle_profile=NULL;config.idle_profile=NULL;
#ifndef VSL_LEGACY_MECHANICAL
        dch_mechanical_amount(s->character,control->mechanical_gain);
#endif
    }
    if(!vi_accept(&s->input,&control->input,0)){vs_engine_destroy(s);return NULL;}
    owner=&s->owner;
#if defined(VSL_DSP_STATIC) && defined(VSL_DSP_FIR_TAPS) && VSL_DSP_FIR_TAPS <= 512
    owner=&vs_runtime_owner;
#endif
    if(!ad_render_init(&s->generator,owner,&config,&adopted)){vs_engine_destroy(s);return NULL;}
#ifdef VSL_DSP_STATIC
    sa_voice_sample_cache(&s->generator.dna,&vs_sample_cache);
    sa_table_init(&vs_table);s->generator.dna.table=&vs_table;
#endif
    if(!vs_events_init(s,&control->events)){vs_engine_destroy(s);return NULL;}
    if(!vs_state_init(s)){vs_engine_destroy(s);return NULL;}
    return s;
}
void vs_engine_destroy(VsEngine *s){if(s){sfl_destroy(s->flare);dch_destroy(s->character);ad_render_dispose(&s->generator);vs_engines_release(s);}}
int vs_engine_set(VsEngine *s,const VsControl *control);
int vs_engine_set_impl(VsEngine *s,const VsControl *control){
    AdControl adopted;ViState input;EcState events;
    if(!s||!control||!vi_valid(&control->input)||control->dna_unified!=s->dna_unified||!dch_control_valid(&control->dna))return 0;
    if(s->dna_unified&&(control->intake_gain!=0||control->air_gain!=0||control->road_gain!=0||control->wind_gain!=0))return 0;
    input=s->input;if(!vi_accept(&input,&control->input,s->generator.frame))return 0;
    events=s->event_control;if(!ec_set(&events,&control->events,s->generator.frame))return 0;
    if(s->flare){
        VsControl dry=*control;
        if(!isfinite(control->startup_gain)||control->startup_gain<0||control->startup_gain>2.6f||
           control->catch_gain!=0||control->legacy_event_gain!=0)return 0;
        dry.startup_gain=dry.catch_gain=dry.legacy_event_gain=0;
        vs_control_to_atlas(&dry,&adopted);
    }else vs_control_to_atlas(control,&adopted);
    if(!ad_render_set(&s->generator,&adopted))return 0;
    if(s->character&&!dch_set(s->character,&control->dna))return 0;
#ifndef VSL_LEGACY_MECHANICAL
    if(s->character)dch_mechanical_amount(s->character,control->mechanical_gain);
#endif
    s->adopted=adopted;s->input=input;s->event_control=events;s->flare_gain=control->startup_gain;return 1;
}
int vs_engine_set(VsEngine *s,const VsControl *control){vsl_perf_enter(12);int result=vs_engine_set_impl(s,control);vsl_perf_leave();return result;}

int vs_engine_process(VsEngine *s,VsOutput *out,unsigned frames);
int vs_engine_process_impl(VsEngine *s,VsOutput *out,unsigned frames){
    AdCapture c={0};float gain;AdSourceDriver driver={s,vs_drive_step,vs_events_sample,NULL};
    if(!s||!vs_output_valid(out,frames))return 0;
    if(!frames)return 1;
    if(s->assets->states)driver.dna=vs_state_sample;
    if(s->character){driver.character=vs_character_sample;driver.envelopes=vs_character_envelopes;}
    if(s->dna_unified)driver.auxiliary=vs_mechanical_sample;
    c.dna=s->dna;c.body=s->body;c.coherent_low=s->low;
    c.residual=s->residual;c.resonant=s->resonant;c.aux_objects=s->aux;
    c.startup=s->startup;c.catch_bloom=s->catching;c.source_added=s->added;
    c.events=s->events;
    /* Unified DNA supplies idle_weight directly in vs_character_sample.
       Its public telemetry reads the owner, not this private sample array. */
    if(!s->character)c.telemetry=s->telemetry;
    gain=s->generator.gain;
    s->event_block_frame=s->generator.frame;
    if(!ad_source_process_controlled(&s->generator,s->monitor,frames,&c,&driver))return 0;
    vs_flare_apply(s,frames,gain);
    if(!s->character)s->idle_weight=s->telemetry[frames-1].idle_weight;
    vs_stems_write(s,out,frames,gain);return 1;
}
int vs_engine_process(VsEngine *s,VsOutput *out,unsigned frames){vsl_perf_enter(0);int result=vs_engine_process_impl(s,out,frames);vsl_perf_leave();return result;}

int vs_engine_telemetry(const VsEngine *s,VsTelemetry *t) {
    const VslDrive *d;
    if(!s||!t)return 0;d=&s->generator.owner->drive;memset(t,0,sizeof *t);
    t->frame=s->generator.frame;t->rpm=d->rpm;t->speed_mps=d->speed_kph/3.6f;
    t->acceleration_mps2=d->vehicle.acceleration_mps2;t->load=d->load;t->gear=d->gear;
    t->root_hz=s->generator.dna.root_hz;t->gain=s->generator.gain;
    t->idle_weight=s->idle_weight;
    t->lifecycle=d->lifecycle;t->operating=d->operating;t->coverage=s->generator.dna.coverage;
    t->shifts=d->shift_events;t->overruns=d->overrun_events;t->legacy_hits=s->generator.owner->events.hits;
    t->input_source=s->input_adopted.value.source;t->input_stale=s->input_adopted.stale;
    t->tire_slip=s->input_adopted.value.tire_slip;t->signal_sequence=s->input_adopted.value.sequence;
    t->event_active=es_pool_active(s->event_runtime);t->event_started=s->event_runtime->started;
    t->event_rejected=s->event_runtime->rejected;t->event_replaced=s->event_runtime->replaced;
    t->event_queue=s->event_control.count;t->event_overflow=s->event_control.overflow;
    t->event_log_lost=s->event_runtime->log_lost;t->event_peak=s->event_runtime->peak_active;
    return 1;
}
