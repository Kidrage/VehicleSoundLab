#include "drive_trace.h"
#include "drive/drive.h"
#include "profiles/voicing.h"
#include "drive/powertrain.h"
#include "drive/shift.h"
#include "drive/fueling.h"
#include "core/engine.h"
#include "core/character.h"
void vsl_trace_header(FILE *f) {
    int i;
    fputs("seconds,lifecycle,operating,rpm,speed_kph,gear,throttle,brake,load,shift_gain,starts,shifts,overruns,hits,acceleration,wheel_coupled_rpm,engine_braking_kph_s,exhaust_gain,body_gain,intake_gain,mechanical_gain,air_gain,high_gain,tilt_delta,cutoff_ratio",f);
    fputs(",clutch_transfer,blip,engine_throttle,engine_throttle_rate,shift_stage,shift_direction,shift_target_rpm,shift_error,aborted_shifts",f);
    for(i=0;i<VSL_LAYERS;++i)fprintf(f,",cut_%s",vsl_layer_name(i));
    for(i=0;i<VSL_OPERATING_COUNT;++i)fprintf(f,",mix_%d",i);
    fputs(",fuel_mode,fuel_command,fuel_closed_seconds,firing_excitation,pumping_excitation",f);
    fputs(",mechanical_motion_gain,mechanical_model_mix,rotating_strikes,fired_strikes,mechanical_stored_energy",f);
    fputs(",combustion_mix,pressure_gain_l,pressure_gain_r,arrival_offset_us_l,arrival_offset_us_r,pressure_events_l,pressure_events_r,modulation_stretch",f);
    fputs(",life_seconds,running_seconds,combustion_permission,lifecycle_flare,drive_rpm_rate",f);
    fputs(",force_gear,force_sample_speed_mps,force_sample_rpm,force_sample_pedal,force_sample_clutch,available_torque_nm,shaft_torque_nm,wheel_force_n,rolling_n,aerodynamic_n,service_brake_n,engine_brake_n,effective_mass_kg,acceleration_mps2",f);
    fputs(",coupling_active,clutch_locked,clutch_capacity_nm,clutch_torque_nm,clutch_slip_rad_s,requested_torque_nm,idle_torque_nm,governor_reduction_nm,engine_work_j,road_work_j,clutch_heat_j,transmission_loss_j,numerical_loss_j,kinetic_before_j,kinetic_after_j,energy_error_j",f);
    fputs(",energy_steps,total_kinetic_delta_j,total_engine_work_j,total_road_work_j,total_clutch_heat_j,total_transmission_loss_j,total_numerical_loss_j,max_energy_error_j",f);
    fputs(",pressure_texture_target,structure_transfer_target,pressure_texture_mix,structure_transfer_mix,character_events,character_pressure_l,character_pressure_r,character_structure",f);
    fputs(",response_shape_target,response_shape_mix,response_pressure_events,response_structure_events",f);
    fputs(",event_color_target,event_color_mix,event_color_events_l,event_color_events_r,event_color_max_mod,firing_source_target,pulse_amount_target,pulse_mix,pulse_variation,pulse_events_l,pulse_events_r,pulse_overflow",f);
    fputc('\n',f);
}
void vsl_trace_frame(FILE *f,const VslEngine *e,double seconds) {
    const VslDrive *d=&e->drive;const VslVoicing *v=&e->voice;int i;
    fprintf(f,"%.6f,%s,%s,%.3f,%.3f,%d,%.5f,%.5f,%.5f,%.5f,%u,%u,%u,%u,%.6f",
        seconds,vsl_lifecycle_name(d->lifecycle),vsl_operating_name(d->operating),
        d->rpm,d->speed_kph,d->gear,d->throttle,d->brake,d->load,d->shift_gain,
        d->start_events,d->shift_events,d->overrun_events,e->events.hits,d->acceleration);
    fprintf(f,",%.5f,%.5f",d->speed_kph*vsl_gear_ratio(d->gear),
        vsl_engine_braking(d,vsl_profile(e->target.profile)->max_rpm));
    fprintf(f,",%.7f,%.7f,%.7f,%.7f,%.7f,%.7f,%.7f,%.7f",v->dna_gain,v->body_gain,
        v->intake_gain,v->mechanical_gain,v->air_gain,v->high_gain,v->tilt_delta,v->cutoff_ratio);
    fprintf(f,",%.7f,%.7f,%.7f,%.7f,%s,%d,%.3f,%.3f,%u",d->clutch_transfer,d->blip,
        d->engine_throttle,d->engine_throttle_rate,vsl_shift_stage_name(d->shift_stage),
        d->shift_direction,d->shift_target_rpm,d->shift_error,d->aborted_shifts);
    for(i=0;i<VSL_LAYERS;++i)fprintf(f,",%.7f",v->cut[i]);
    for(i=0;i<VSL_OPERATING_COUNT;++i)fprintf(f,",%.7f",v->state_mix[i]);
    fprintf(f,",%s,%.7f,%.7f,%.7f,%.7f",vsl_fuel_mode_name(d->fuel.mode),d->fuel.command,
        d->fuel.closed_seconds,e->excitation.firing,e->excitation.pumping);
    fprintf(f,",%.7f,%.7f,%u,%u,%.12g",v->mechanical_motion_gain,e->mechanical.mix,
        e->mechanical.rotating_strikes,e->mechanical.fired_strikes,e->mechanical.stored_energy);
    fprintf(f,",%.7f,%.7f,%.7f,%.7f,%.7f,%u,%u,%.7f",e->combustion.mix,
        e->combustion.gain[0],e->combustion.gain[1],e->control.rpm>0?-e->combustion.phase_delta[0]/(2*VSL_PI*e->control.rpm/120)*1e6:0,
        e->control.rpm>0?-e->combustion.phase_delta[1]/(2*VSL_PI*e->control.rpm/120)*1e6:0,
        e->combustion.events[0],e->combustion.events[1],e->combustion.stretch);
    fprintf(f,",%.7f,%.7f,%.7f,%.7f,%.7f",d->life_seconds,d->running_seconds,d->combustion,d->lifecycle_flare,d->rpm_rate);
    {
        const VslVehicle *p=&d->vehicle;
        fprintf(f,",%d,%.7f,%.7f,%.7f,%.7f,%.7f,%.7f,%.7f,%.7f,%.7f,%.7f,%.7f,%.7f,%.7f",
            p->transmitted_gear,p->sample_speed_mps,p->sample_rpm,p->sample_pedal,p->sample_clutch,
            p->available_torque_nm,p->shaft_torque_nm,p->wheel_force_n,p->rolling_n,p->aerodynamic_n,
            p->service_brake_n,p->engine_brake_n,p->effective_mass_kg,p->acceleration_mps2);
        fprintf(f,",%d,%d,%.12g,%.12g,%.12g,%.12g,%.12g,%.12g,%.12g,%.12g,%.12g,%.12g,%.12g,%.12g,%.12g,%.12g",
            p->solver_active,p->clutch_locked,p->clutch_capacity_nm,p->clutch_torque_nm,p->clutch_slip_rad_s,
            p->requested_torque_nm,p->idle_torque_nm,p->governor_reduction_nm,p->engine_work_j,p->road_work_j,
            p->clutch_heat_j,p->transmission_loss_j,p->numerical_loss_j,p->energy_before_j,p->energy_after_j,p->energy_error_j);
        {
            const VslCouplingAudit *a=&d->coupling_audit;
            fprintf(f,",%u,%.12g,%.12g,%.12g,%.12g,%.12g,%.12g,%.12g",a->steps,a->kinetic_delta_j,
                a->engine_work_j,a->road_work_j,a->clutch_heat_j,a->transmission_loss_j,a->numerical_loss_j,a->max_energy_error_j);
        }
    }
    fprintf(f,",%.12g,%.12g,%.12g,%.12g,%u,%.12g,%.12g,%.12g",e->target.pressure_texture,e->target.structure_transfer,
        e->character.amount_pressure,e->character.amount_structure,vsl_character_events(&e->character),
        e->character.added[0],e->character.added[1],e->character.added[2]);
    fprintf(f,",%.12g,%.12g,%llu,%llu",e->target.response_shape,e->response.amount,
        (unsigned long long)e->response.pressure_events,(unsigned long long)e->response.structure_events);
    fprintf(f,",%.12g,%.12g,%llu,%llu,%.12g",e->target.event_color,e->color.amount,
        (unsigned long long)e->color.events[0],(unsigned long long)e->color.events[1],e->color.max_mod);
    fprintf(f,",%d,%.12g,%.12g,%.12g,%llu,%llu,%u",e->target.firing_source,e->target.pulse_amount,e->firing_source.mix,e->firing_source.variation,
        (unsigned long long)e->firing_source.accepted[0],(unsigned long long)e->firing_source.accepted[1],e->firing_source.kernel.overflow);
    fputc('\n',f);
}
