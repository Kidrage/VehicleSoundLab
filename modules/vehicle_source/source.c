#include "internal.h"
#include "atlas_drive/source_process.h"
#include <stdlib.h>
#include <string.h>
VsEngine *vs_engine_create(const VsAssets *assets,const VsControl *control) {
    VsEngine *s;AdControl adopted;AdConfig config;
    if(!assets||!control||!vi_valid(&control->input)||!ec_control_valid(&control->events)||
       (control->dna_unified!=0&&control->dna_unified!=1)||!dch_control_valid(&control->dna))return NULL;
    vs_control_to_atlas(control,&adopted);
    if(!ad_control_supported(&assets->owned.config,&adopted))return NULL;
    s=calloc(1,sizeof *s);if(!s)return NULL;
    s->assets=assets;s->adopted=adopted;
    config=assets->owned.config;s->dna_unified=control->dna_unified;
    if(s->dna_unified){
        s->character=dch_create(config.fine_idle_profile,config.seed,&control->dna);
        if(!s->character){free(s);return NULL;}
        config.fine_idle_profile=NULL;config.idle_profile=NULL;
    }
    if(!vi_accept(&s->input,&control->input,0)){vs_engine_destroy(s);return NULL;}
    if(!ad_render_init(&s->generator,&s->owner,&config,&adopted)){vs_engine_destroy(s);return NULL;}
    if(!vs_events_init(s,&control->events)){vs_engine_destroy(s);return NULL;}
    if(!vs_state_init(s)){vs_engine_destroy(s);return NULL;}
    return s;
}
void vs_engine_destroy(VsEngine *s){if(s){dch_destroy(s->character);ad_render_dispose(&s->generator);free(s);}}
int vs_engine_set(VsEngine *s,const VsControl *control) {
    AdControl adopted;ViState input;EcState events;
    if(!s||!control||!vi_valid(&control->input)||control->dna_unified!=s->dna_unified||!dch_control_valid(&control->dna))return 0;
    input=s->input;if(!vi_accept(&input,&control->input,s->generator.frame))return 0;
    events=s->event_control;if(!ec_set(&events,&control->events,s->generator.frame))return 0;
    vs_control_to_atlas(control,&adopted);
    if(!ad_render_set(&s->generator,&adopted))return 0;
    if(s->character&&!dch_set(s->character,&control->dna))return 0;
    s->adopted=adopted;s->input=input;s->event_control=events;return 1;
}
int vs_engine_process(VsEngine *s,VsOutput *out,unsigned frames) {
    AdCapture c={0};double gain;AdSourceDriver driver={s,vs_drive_step,vs_events_sample,NULL};
    if(!s||!vs_output_valid(out,frames))return 0;
    if(!frames)return 1;
    if(s->assets->states)driver.dna=vs_state_sample;
    if(s->character)driver.character=vs_character_sample;
    c.dna=s->dna;c.body=s->body;c.coherent_low=s->low;
    c.residual=s->residual;c.resonant=s->resonant;c.aux_objects=s->aux;
    c.startup=s->startup;c.catch_bloom=s->catching;c.source_added=s->added;
    c.events=s->events;c.telemetry=s->telemetry;
    gain=s->generator.gain;
    s->event_block_frame=s->generator.frame;
    if(!ad_source_process_controlled(&s->generator,s->monitor,frames,&c,&driver))return 0;
    if(!s->character)s->idle_weight=s->telemetry[frames-1].idle_weight;
    vs_stems_write(s,out,frames,gain);return 1;
}
int vs_engine_telemetry(const VsEngine *s,VsTelemetry *t) {
    const VslDrive *d;
    if(!s||!t)return 0;d=&s->owner.drive;memset(t,0,sizeof *t);
    t->frame=s->generator.frame;t->rpm=d->rpm;t->speed_mps=d->speed_kph/3.6;
    t->acceleration_mps2=d->vehicle.acceleration_mps2;t->load=d->load;t->gear=d->gear;
    t->root_hz=s->generator.dna.root_hz;t->gain=s->generator.gain;
    t->idle_weight=s->idle_weight;
    t->lifecycle=d->lifecycle;t->operating=d->operating;t->coverage=s->generator.dna.coverage;
    t->shifts=d->shift_events;t->overruns=d->overrun_events;t->legacy_hits=s->owner.events.hits;
    t->input_source=s->input_adopted.value.source;t->input_stale=s->input_adopted.stale;
    t->tire_slip=s->input_adopted.value.tire_slip;t->signal_sequence=s->input_adopted.value.sequence;
    t->event_active=es_pool_active(&s->event_pool);t->event_started=s->event_pool.started;
    t->event_rejected=s->event_pool.rejected;t->event_replaced=s->event_pool.replaced;
    t->event_queue=s->event_control.count;t->event_overflow=s->event_control.overflow;
    t->event_log_lost=s->event_pool.log_lost;t->event_peak=s->event_pool.peak_active;
    return 1;
}
