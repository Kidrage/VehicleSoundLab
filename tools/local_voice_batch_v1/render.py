"""Explicit offline export protocol dispatch; DSP remains in existing C modules."""
RAW_PROTOCOL = 'vsl.sound-dna-raw-export/1'
BANDLIMITED_PROTOCOL = 'vsl.sound-dna-bandlimited-export/1'


def playback_argument(protocol, root_hz):
    if protocol == RAW_PROTOCOL:
        return 1
    if protocol == BANDLIMITED_PROTOCOL:
        if not 5 <= root_hz <= 1000:
            raise ValueError('Bandlimited profile base must be5..1000Hz')
        return root_hz
    raise ValueError('Unsupported export protocol: '+str(protocol))
