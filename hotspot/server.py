import json
import secrets
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlsplit
from .common import BASE, canonical, GateError
from .service import dispatch

STATIC=BASE/'hotspot/static'

def make_server(store,port=8776):
    token=secrets.token_urlsafe(32)
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,fmt,*args):pass
        def reply(self,code,body,kind='application/json; charset=utf-8'):
            self.send_response(code);self.send_header('Content-Type',kind)
            self.send_header('Content-Length',str(len(body)));self.send_header('Cache-Control','no-store')
            self.send_header('X-Content-Type-Options','nosniff')
            self.send_header('Content-Security-Policy',"default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; frame-ancestors 'none'; base-uri 'none'")
            self.end_headers();self.wfile.write(body)
        def valid_host(self):
            return self.headers.get('Host') in (f'127.0.0.1:{self.server.server_port}',f'localhost:{self.server.server_port}')
        def do_GET(self):
            if not self.valid_host():return self.reply(403,b'{}')
            path=urlsplit(self.path).path
            if path=='/api/state':return self.reply(200,canonical({'csrf':token,**dispatch(store,'overview',{})}))
            files={'/':'index.html','/app.js':'app.js','/style.css':'style.css'}
            if path not in files:return self.reply(404,b'{}')
            p=STATIC/files[path]
            kind={'.html':'text/html; charset=utf-8','.js':'text/javascript; charset=utf-8','.css':'text/css; charset=utf-8'}[p.suffix]
            self.reply(200,p.read_bytes(),kind)
        def do_POST(self):
            if not self.valid_host() or self.headers.get('X-CSRF-Token')!=token:return self.reply(403,canonical({'error':'请求校验失败，请刷新本地页面'}))
            if self.headers.get('Origin') not in (f'http://127.0.0.1:{self.server.server_port}',f'http://localhost:{self.server.server_port}',None):return self.reply(403,b'{}')
            try:
                length=int(self.headers.get('Content-Length','0'))
                if not 0<length<=2_000_000:raise ValueError('请求长度无效，最大2MB')
                if self.headers.get_content_type()!='application/json':raise ValueError('仅接受JSON')
                data=json.loads(self.rfile.read(length)); action=urlsplit(self.path).path.removeprefix('/api/')
                result=dispatch(store,action,data)
                self.reply(200,canonical({'result':result}))
            except (ValueError,KeyError,TypeError,OSError) as exc:self.reply(400,canonical({'error':str(exc)}))
    return HTTPServer(('127.0.0.1',port),Handler)

def serve(store,port=8776):
    server=make_server(store,port)
    print(f'热点中心 http://127.0.0.1:{server.server_port} / 环境 {store.environment}',flush=True)
    try:server.serve_forever()
    except KeyboardInterrupt:pass
    finally:server.server_close()
