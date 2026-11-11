"""Freeze verified driving-take tools without changing historical sound."""
from freeze_review import freeze
if __name__=='__main__':
    freeze('0.15.0','v015',17,'research/V015驾驶录制.md',
        'Frozen deterministic actual-driving recording/replay review. Sound/drive source algorithms unchanged from V014. Subjective V10 realism, identified full vehicle and actual array listening remain unaccepted; broad goal active.',
        'ac2b37d8639027d79934a2023cf8d1d37d3b2f96')
