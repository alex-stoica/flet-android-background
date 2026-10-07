import tempfile
import unittest
from pathlib import Path
import xml.etree.ElementTree as ET

from flet_android_background.android import ANDROID, NAME, configure_android_project


class AndroidConfigurationTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.project = Path(self.directory.name)
        self.manifest = self.project / 'android/app/src/main/AndroidManifest.xml'
        self.manifest.parent.mkdir(parents=True)
        self.manifest.write_text('<manifest><application /></manifest>')

    def test_data_sync_is_idempotent(self):
        for _ in range(2):
            configure_android_project(self.project, service_type='dataSync')
        root = ET.parse(self.manifest).getroot()
        self.assertEqual(len(root.findall('application/service')), 1)
        self.assertEqual(len(root.findall('uses-permission')), 1)
        self.assertEqual(root.find('uses-permission').get(NAME),
                         'android.permission.FOREGROUND_SERVICE_DATA_SYNC')

    def test_special_use_requires_explanation_without_changing_manifest(self):
        before = self.manifest.read_bytes()
        with self.assertRaises(ValueError):
            configure_android_project(self.project, service_type='specialUse')
        self.assertEqual(self.manifest.read_bytes(), before)

    def test_switching_type_removes_special_use_property(self):
        configure_android_project(self.project, service_type='specialUse', subtype='Example & purpose')
        configure_android_project(self.project, service_type='shortService')
        service = ET.parse(self.manifest).find('application/service')
        self.assertEqual(service.get(f'{{{ANDROID}}}foregroundServiceType'), 'shortService')
        self.assertIsNone(service.find('property'))

    def test_unsupported_type_rejected(self):
        with self.assertRaises(ValueError):
            configure_android_project(self.project, service_type='camera')
