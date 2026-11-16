"""Use the existing C raw exporter; no Python or browser oscillator substitute."""
import subprocess
import numpy as np
import soundfile as sf
from research_archive_v1 import sha


def preview(repo,model,out,p):
    exe=repo/'build-sound-dna-export-v1/bin/Release/sound_dna_export.exe'
    if not exe.exists():
        raise ValueError('缺少现有C试听导出器，请先运行 Build-Sound-Designer.ps1')
    command=list(map(str,[exe,model,out,p['seconds'],p['pitch'],p['detail'],p['seed'],512]))
    result=subprocess.run(command,cwd=repo,capture_output=True,timeout=90,creationflags=0x08000000)
    if result.returncode:
        raise ValueError('C声源拒绝了参数；请降低幅度或检查基频／阶数')
    audio,rate=sf.read(out,always_2d=True)
    if rate!=48000 or not np.isfinite(audio).all(): raise ValueError('C输出无效')
    peak=float(np.max(abs(audio)))
    return dict(peak=peak,frames=len(audio),sample_rate=rate,channels=2,
                rms_dbfs=float(20*np.log10(max(np.sqrt(np.mean(audio**2)),1e-12))),
                overload=peak>=1,model_sha256=sha(model),renderer_sha256=sha(exe),
                processing='现有C Sound DNA；参数域增益／声线编辑；无混响、限幅或自动响度匹配')
