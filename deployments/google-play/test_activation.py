"""Ensure delayed Google permissions never open an unverified checkout."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

spec=importlib.util.spec_from_file_location('mca_play_setup_test',Path(__file__).with_name('setup.py'))
setup=importlib.util.module_from_spec(spec)
spec.loader.exec_module(setup)

class ActivationTests(unittest.TestCase):
    def setUp(self):
        self.folder=tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.status=Path(self.folder.name)/'state.json'
        self.status.write_text(json.dumps({'state':'pending','deadline':2000}))
        self.patches=[]
        for name,value in [('ACTIVATION_STATUS',self.status),('safe_file',lambda _:None),
                           ('env_read',lambda:{'MCA_PLAY_ENABLED':'false'})]:
            p=patch.object(setup,name,value); p.start(); self.addCleanup(p.stop)
        p=patch.object(setup.time,'time',return_value=1000); p.start();self.addCleanup(p.stop)

    def test_denied_permissions_leave_checkout_disabled(self):
        with patch.object(setup,'probe',side_effect=ValueError('401 permissionDenied')), \
             patch.object(setup,'activate') as activate, patch.object(setup,'student') as student:
            setup.retry_activation()
            activate.assert_not_called()
            student.assert_not_called()
        self.assertEqual(json.loads(self.status.read_text())['state'],'pending')

    def test_expired_wait_never_activates(self):
        self.status.write_text(json.dumps({'state':'pending','deadline':999}))
        with patch.object(setup,'probe') as probe, patch.object(setup.pay,'run') as run:
            setup.retry_activation()
            probe.assert_not_called()
            run.assert_called_once_with('systemctl','stop',setup.ACTIVATION_TIMER)
        self.assertEqual(json.loads(self.status.read_text())['state'],'expired')

    def test_student_verification_failure_closes_checkout(self):
        with patch.object(setup,'probe'), patch.object(setup,'activate'), \
             patch.object(setup,'student',side_effect=ValueError('student config failed')), \
             patch.object(setup,'disable_purchasing') as close:
            setup.retry_activation()
            close.assert_called_once_with()
        self.assertEqual(json.loads(self.status.read_text())['state'],'pending')

    def test_success_verifies_student_then_stops_retry(self):
        with patch.object(setup,'probe'), patch.object(setup,'activate'), \
             patch.object(setup,'student') as student, patch.object(setup.pay,'run') as run:
            setup.retry_activation()
            student.assert_called_once_with('test')
            run.assert_called_once_with('systemctl','stop',setup.ACTIVATION_TIMER)
        self.assertEqual(json.loads(self.status.read_text())['state'],'active')

if __name__=='__main__': unittest.main()
