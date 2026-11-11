#include "source.h"
#include <math.h>
#include <string.h>

static int unit(double x) { return isfinite(x) && x >= 0 && x <= 1; }

int ds_source_control_valid(const DsSourceControl *c) {
    return c && isfinite(c->pitch) && c->pitch >= .9 && c->pitch <= 1.1 &&
        unit(c->dna_detail) && unit(c->low_detail) && unit(c->dna_gain) && unit(c->low_gain);
}

int ds_source_init(DsSource *s, const DsSourceConfig *c, const DsSourceControl *p) {
    if (!s || !c || !c->dna || !ds_source_control_valid(p) ||
        !isfinite(c->low_scale) || c->low_scale < 0 || c->low_scale > 4) return 0;
    /* This adapter supports a phase-aligned pair in one acoustic coordinate.
       It does not infer engine orders, RPM or a root mapping between models. */
    if (c->low && (c->low->base_hz != c->dna->base_hz ||
        c->low->rate != c->dna->rate || c->low->window != c->dna->window ||
        c->low->hop != c->dna->hop)) return 0;
    memset(s, 0, sizeof *s);
    if (!sd_voice_init(&s->dna, c->dna, c->dna_seed, p->pitch, p->dna_detail, 1)) return 0;
    if (c->low && !sd_voice_init(&s->low, c->low, c->low_seed, p->pitch, p->low_detail, 1)) return 0;
    s->has_low = c->low != NULL;
    s->target = *p;
    s->dna_gain = p->dna_gain;
    s->low_gain = p->low_gain;
    s->low_scale = c->low_scale;
    s->follow = 1 - exp(-1 / (.018 * c->dna->rate));
    return 1;
}

int ds_source_set(DsSource *s, const DsSourceControl *c) {
    if (!s || !s->dna.model || !ds_source_control_valid(c)) return 0;
    sd_voice_set(&s->dna, c->pitch, c->dna_detail, 1);
    if (s->has_low) sd_voice_set(&s->low, c->pitch, c->low_detail, 1);
    s->target = *c;
    return 1;
}

void ds_source_tick(DsSource *s, DsSourceFrame *f) {
    int c;
    sd_voice_process(&s->dna, f->dna_raw, 1);
    f->low_raw[0] = f->low_raw[1] = 0;
    /* Muting a layer never pauses its clock or its random process. */
    if (s->has_low) sd_voice_process(&s->low, f->low_raw, 1);
    s->dna_gain += s->follow * (s->target.dna_gain - s->dna_gain);
    s->low_gain += s->follow * (s->target.low_gain - s->low_gain);
    for (c = 0; c < 2; ++c) {
        f->dna[c] = f->dna_raw[c] * s->dna_gain;
        f->low[c] = f->low_raw[c] * s->low_scale * s->low_gain;
    }
    ++s->frame;
}
