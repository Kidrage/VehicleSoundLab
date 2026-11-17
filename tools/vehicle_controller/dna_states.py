"""Presentation of C state telemetry; never derives or selects driving states."""
LABELS=('默认','怠速','给油','收油')


def describe_blend(value):
    if not value:return '等待驾驶器状态'
    parts=[]
    for k,label in enumerate(LABELS):
        if value['weight'][k]>.005:
            parts.append(f"{label} {value['weight'][k]*100:.0f}%"+('（外推）' if value['coverage'][k] else ''))
    return '当前DNA：'+' / '.join(parts)
