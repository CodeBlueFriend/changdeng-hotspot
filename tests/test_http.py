import json
import tempfile
import threading
import unittest
import urllib.request
import urllib.error
from hotspot.store import Store
from hotspot.server import make_server

class HTTPTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.server=make_server(Store(self.tmp.name,'test'),0)
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start()
        self.addCleanup(self.stop)
        self.base=f'http://127.0.0.1:{self.server.server_port}'
    def stop(self):self.server.shutdown();self.thread.join();self.server.server_close()
    def test_json_api_persistence_and_csrf(self):
        state=json.load(urllib.request.urlopen(self.base+'/api/state'))
        self.assertEqual(state['environment'],'test')
        body=json.dumps({'title':'【构造样例】网页导入','is_fixture':True}).encode()
        req=urllib.request.Request(self.base+'/api/manual',body,{'Content-Type':'application/json','X-CSRF-Token':state['csrf']})
        response=json.load(urllib.request.urlopen(req));self.assertEqual(response['result']['status'],'valid')
        self.assertEqual(len(json.load(urllib.request.urlopen(self.base+'/api/state'))['snapshots']),1)
        with self.assertRaises(urllib.error.HTTPError) as error:urllib.request.urlopen(urllib.request.Request(self.base+'/api/manual',body,{'Content-Type':'application/json'}))
        self.assertEqual(error.exception.code,403)
    def test_external_host_and_origin_blocked(self):
        with self.assertRaises(urllib.error.HTTPError):urllib.request.urlopen(urllib.request.Request(self.base+'/api/state',headers={'Host':'attacker.example'}))
        state=json.load(urllib.request.urlopen(self.base+'/api/state'))
        with self.assertRaises(urllib.error.HTTPError):urllib.request.urlopen(urllib.request.Request(self.base+'/api/collect',b'{}',{'Content-Type':'application/json','X-CSRF-Token':state['csrf'],'Origin':'https://attacker.example'}))
    def test_static_security_headers(self):
        response=urllib.request.urlopen(self.base+'/');self.assertIn('frame-ancestors',response.headers['Content-Security-Policy']);self.assertIn('热点中心',response.read().decode())

if __name__=='__main__':unittest.main()
