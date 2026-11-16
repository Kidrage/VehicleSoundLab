"""Loopback-only local UI with one serialized background authoring worker."""
from concurrent.futures import ThreadPoolExecutor
import json
import mimetypes
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path
import subprocess
import threading
import uuid
from urllib.parse import urlparse,unquote

from .workspace import Workspace


def serve(repo,root,port):
    workspace=Workspace(repo,root);assets=repo/'tools/sound_designer/web'
    worker=ThreadPoolExecutor(max_workers=1);jobs={};lock=threading.Lock()

    def submit(action,data):
        key=uuid.uuid4().hex
        with lock: jobs[key]=dict(status='queued')
        def run():
            with lock: jobs[key]=dict(status='running')
            try: result=action(data);value=dict(status='done',result=result)
            except Exception as error: value=dict(status='error',error=str(error))
            with lock: jobs[key]=value
        worker.submit(run)
        return key

    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args): pass
        def json(self,value,status=200):
            raw=json.dumps(value,ensure_ascii=False,allow_nan=False).encode('utf-8')
            self.send_response(status);self.send_header('Content-Type','application/json; charset=utf-8')
            self.send_header('Content-Length',str(len(raw)));self.end_headers();self.wfile.write(raw)
        def do_GET(self):
            try:
                path=unquote(urlparse(self.path).path)
                if path.startswith('/api/job/'):
                    with lock: value=jobs.get(path.rsplit('/',1)[-1],dict(status='error',error='任务不存在'))
                    return self.json(value)
                if path=='/api/config':
                    return self.json(dict(schema='vsl.sound-designer-server/1',root=str(workspace.root),renderer='现有C Sound DNA',version=1))
                if path=='/api/projects':
                    return self.json(workspace.projects())
                if path.startswith('/api/parameters/'):
                    return self.json(workspace.parameters(path.rsplit('/',1)[-1]))
                if path.startswith('/api/project/'):
                    return self.json(workspace.view(path.rsplit('/',1)[-1]))
                if path.startswith('/files/'):
                    target=(workspace.root/path[len('/files/'):]).resolve()
                    if not target.is_relative_to(workspace.root.resolve()): raise ValueError('无效文件路径')
                else:
                    target=(assets/('index.html' if path=='/' else path.lstrip('/'))).resolve()
                    if not target.is_relative_to(assets.resolve()): raise ValueError('无效页面路径')
                if not target.is_file(): return self.json(dict(error='文件不存在'),404)
                size=target.stat().st_size;self.send_response(200)
                self.send_header('Content-Type',mimetypes.guess_type(target.name)[0] or 'application/octet-stream')
                self.send_header('Content-Length',str(size));self.send_header('Cache-Control','no-store');self.end_headers()
                with target.open('rb') as stream:
                    while chunk:=stream.read(1024**2): self.wfile.write(chunk)
            except (BrokenPipeError,ConnectionResetError): pass
            except Exception as error: self.json(dict(error=str(error)),400)
        def do_POST(self):
            try:
                origin=self.headers.get('Origin')
                if origin and urlparse(origin).netloc!=self.headers.get('Host'): raise ValueError('请求来源不匹配')
                length=int(self.headers.get('Content-Length','0'))
                if not 0<length<=68*1024**2: raise ValueError('请求过大或为空')
                data=json.loads(self.rfile.read(length))
                actions={'/api/new':workspace.create,'/api/analyze':workspace.analyze,
                         '/api/compile':workspace.compile,'/api/render':workspace.render,'/api/save':workspace.save_design}
                if self.path=='/api/driver':
                    exe=repo/'build-catalog-local-v1/bin/Release/VslAtlasMonitor.exe'
                    if not exe.exists(): raise ValueError('请先构建原生音色目录')
                    subprocess.Popen([str(exe),'--catalog'],cwd=repo,creationflags=0x08000000)
                    return self.json(dict(opened=True))
                if self.path not in actions: return self.json(dict(error='接口不存在'),404)
                self.json(dict(job=submit(actions[self.path],data)),202)
            except Exception as error: self.json(dict(error=str(error)),400)

    server=ThreadingHTTPServer(('127.0.0.1',port),Handler)
    print(f'SOUND_DESIGNER_READY http://127.0.0.1:{port}',flush=True)
    server.serve_forever()
