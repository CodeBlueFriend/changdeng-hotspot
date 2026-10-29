import json
import unittest
from pathlib import Path
from test_workflow import WorkflowTests
from hotspot.common import write, GateError
from hotspot.review import gate
from hotspot.exporter import export_candidate, audit

class DependencyTests(unittest.TestCase):
    def setUp(self):
        self.helper=WorkflowTests();self.helper.setUp();self.addCleanup(self.helper.doCleanups)
    def test_config_change_invalidates_review(self):
        h=self.helper;c=h.ready();h.approve(c)
        write(h.store.project/'00_项目配置/内容选题偏好.json',{'duration_minutes':[15,40]})
        self.assertFalse(gate(h.store,c['candidate_id'])['eligible'])
    def test_export_recovers_after_receipt_commit_gap(self):
        h=self.helper;c=h.ready();h.approve(c);a=export_candidate(h.store,c['candidate_id'],'history_long_video','user',True)
        # Simulate a crash after durable file rename but before receipt transaction commit.
        with h.store.db() as db:db.execute('DELETE FROM receipts')
        b=export_candidate(h.store,c['candidate_id'],'history_long_video','user',True)
        self.assertEqual(a['receipt_id'],b['receipt_id']);self.assertEqual(a['inbox'],b['inbox'])
    def test_modified_bundle_does_not_silently_repair(self):
        h=self.helper;c=h.ready();h.approve(c);a=export_candidate(h.store,c['candidate_id'],'history_long_video','user',True)
        (Path(a['inbox'])/'candidate.json').write_text('{}')
        with self.assertRaises(GateError):export_candidate(h.store,c['candidate_id'],'history_long_video','user',True)
        self.assertTrue(audit(h.store)['affected_exports'])

# Imported TestCase is only a fixture helper, not a second copy of the suite.
def load_tests(loader,tests,pattern):return loader.loadTestsFromTestCase(DependencyTests)
