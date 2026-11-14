"""Text inputs for the offline adapter; no synthesis or driver implementation."""
from pathlib import Path
import numpy as np
from sound_dna.profile import export


def manifest(path, models, alignment=32):
    Path(path).write_text('VSL_LOCAL_ATLAS 1 %d %d\n' % (len(models), alignment)+
                          ''.join(str(Path(p).resolve())+'\n' for p in models), encoding='utf-8', newline='\n')


def trace(path, low, high, plan):
    spec = plan['trace']
    frames = np.arange(0, spec['frames'], spec['event_hop'])
    position = np.interp(frames/48000, spec['knots_seconds'], spec['knots_position'])
    roots = low+(high-low)*position
    Path(path).write_text('VSL_LOCAL_ATLAS_TRACE 1 %d %d\n' % (spec['frames'], len(frames))+
        ''.join('%d %.17g %.17g %.17g\n' % (f, hz, spec['detail'], spec['gain'])
                for f, hz in zip(frames, roots)), encoding='utf-8', newline='\n')
    return np.column_stack((frames, roots, np.full(len(frames), spec['detail']), np.full(len(frames), spec['gain'])))


def known(folder, plan):
    folder.mkdir(exist_ok=False)
    paths = []
    for anchor, (root, origin) in enumerate(((60, 0), (64, .47), (68, -.31))):
        model = dict(mean=np.zeros((32, 4)), basis=np.zeros((32, 0, 4)), rho=np.zeros(0),
                     residual_rho=np.zeros(32), root=np.zeros((32, 4, 4)))
        for order, amplitude in ((3, .12), (5, .08), (7, .04), (12, .02)):
            phase = .13*order+origin*order
            al = amplitude*(1+.2*anchor)
            model['mean'][order-1] = [al*np.cos(phase), al*np.sin(phase),
                                     .7*al*np.cos(phase+.4), .7*al*np.sin(phase+.4)]
        path = folder/('known%d.model' % anchor)
        export(path, model, root)
        paths.append(path)
    manifest(folder/'known.manifest', paths)
    trace(folder/'known.trace', 60, 68, plan)
    manifest(folder/'bad.manifest', paths[::-1])
    (folder/'bad.trace').write_text('VSL_LOCAL_ATLAS_TRACE 1 48000 2\n0 60 1 1\n0 64 1 1\n', encoding='utf-8')
    return paths
