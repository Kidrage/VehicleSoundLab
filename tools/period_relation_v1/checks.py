"""Known algebraic positives, counterexamples and subharmonic ambiguity."""
from .intervals import compatible


def specs():
    return [
        ('integer_harmonics_smaller_base_ambiguous',[75.,112.5,187.5],[37.5],.01,[True,True]),
        ('fifth_grid_extra_line',[75.,112.5,187.5],[82.5,37.5],.01,[False,True]),
        ('independent_extra_line',[75.,112.5,187.5],[82.1,37.5],.01,[False,False]),
        ('missing_fundamental_ambiguous',[75.,112.5,187.5],[],.01,[True,True]),
        ('inconsistent_anchors',[75.,112.5,190.],[],.01,[False,False]),
        ('unrelated_frequency_list',[63.,101.,179.],[],.01,[False,False]),
        ('rounded_bin_boundary',[75.,112.,188.],[82.,37.],.5,[False,True])]


def controls():
    rows=[]
    for name,anchors,extras,width,expected in specs():
        values=[compatible(anchors,orders,extras,width) for orders in ([2,3,5],[10,15,25])]
        rows.append(dict(id=name,passed=[value['compatible'] for value in values]==expected,
                         results=values,expected=expected))
    return dict(passed=all(row['passed'] for row in rows),cases=rows,
        scope='Interval algebra only, not qualification of spectral frequency uncertainty or a general waveform period detector')
