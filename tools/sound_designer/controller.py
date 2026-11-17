"""Launch one independent controller process; preserve launch diagnostics."""
from pathlib import Path
import subprocess
import sys
import threading
import uuid


class Controller:
    def __init__(self,repo,workspace):
        self.repo=Path(repo);self.workspace=Path(workspace);self.process=None;self.lock=threading.Lock();self.ready=None

    def open(self):
        with self.lock:
            if self.process is not None and self.process.poll() is None:
                return dict(opened=True,already_open=True,pid=self.process.pid,controller='source-only',revision=15,independent_window=True,ready=str(self.ready))
            library=self.repo/'build-vehicle-source-v13/bin/Release/vsl_source_bridge.dll'
            if not library.is_file():raise ValueError('请先运行 Build-Vehicle-Source.ps1 构建声源控制模块')
            self.workspace.mkdir(parents=True,exist_ok=True);identity=uuid.uuid4().hex
            self.ready=self.workspace/(identity+'.ready.json');log=self.workspace/(identity+'.launch.log')
            with log.open('wb') as output:
                self.process=subprocess.Popen([sys.executable,str(self.repo/'tools/run_vehicle_controller.py'),
                    '--workspace',str(self.workspace),'--ready-file',str(self.ready)],cwd=self.repo,creationflags=0x08000000,
                    stdout=output,stderr=subprocess.STDOUT)
            return dict(opened=True,already_open=False,pid=self.process.pid,controller='source-only',revision=15,independent_window=True,ready=str(self.ready))
