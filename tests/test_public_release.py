import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from hotspot.common import BASE, read, validate
from hotspot.store import Store
from hotspot.acquisition import import_manual
from hotspot.review import create_candidate

class PublicReleaseTests(unittest.TestCase):
    def test_public_examples_and_template(self):
        template=read(BASE/'examples/candidate.template.json')
        validate('candidate',template)
        with tempfile.TemporaryDirectory() as root:
            store=Store(root,'test')
            s=import_manual(store,read(BASE/'examples/manual.fixture.json'))
            c=create_candidate(store,s['snapshot_id'],s['records'][0]['record_id'],'test-author')
            validate('candidate',c)
            self.assertTrue(c['is_fixture'])
            self.assertFalse(c['export']['eligible'])
    def test_cli_from_unrelated_working_directory(self):
        import os
        with tempfile.TemporaryDirectory() as root:
            env=dict(os.environ,PYTHONPATH=str(BASE))
            r=subprocess.run([sys.executable,'-m','hotspot','--project',root,'--environment','test','status'],cwd=root,env=env,capture_output=True,text=True)
            self.assertEqual(r.returncode,0,r.stderr)
            self.assertIn('NOT_CONFIGURED',r.stdout)
    def test_runtime_has_no_private_handoff_dependency(self):
        for p in (BASE/'hotspot').glob('*.py'):
            self.assertNotIn('handoff/',p.read_text(),str(p))

if __name__=='__main__':unittest.main()
