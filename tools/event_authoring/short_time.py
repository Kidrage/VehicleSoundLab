"""Declared short-event observation resolution, separate from runtime synthesis."""
RATE = 48000
MIN_FRAMES = 384  #8ms; at least five4ms STFT frames.
LONG_MIN_FRAMES = 2880


def layout(frames):
    if frames < MIN_FRAMES:
        raise ValueError('One short event must contain at least8ms')
    return (960,720) if frames >= LONG_MIN_FRAMES else (192,144)
