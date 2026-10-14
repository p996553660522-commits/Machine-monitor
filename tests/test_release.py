"""Release packaging, fixed versions and non-destructive publishing regressions."""
import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zipfile

from scripts import release as r


class ReleaseTests(unittest.TestCase):
    def setUp(self):
        self.item = json.loads((r.ROOT / "releases.json").read_text())["releases"][2]
        self.files = {
            r.COMPONENT + "manifest.json": b'{"version":"1.4.0"}',
            r.COMPONENT + "storage.py": b'data = {"history_schema_version": 4}',
            r.COMPONENT + "tests/test_example.py": b'assert True',
            r.COMPONENT + ".storage/private": b'private history',
            r.COMPONENT + "secrets.yaml": b'private settings',
            "firmware/MachineMonitor/MachineMonitor.ino": b'payload += "\\"sw_version\\":\\"1.2.1\\"";',
            "docs/FIRMWARE_RU.md": b'Firmware instructions',
            ".env": b'private environment',
        }

    def test_exact_install_layout_and_no_user_data(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = r.build(self.item, self.files, Path(tmp), b'Notes')
            with zipfile.ZipFile(directory / "machine-monitor-1.4.0.zip") as archive:
                names = archive.namelist()
                self.assertTrue(all(i.create_system == 3 for i in archive.infolist()))
                self.assertIn(r.COMPONENT + "manifest.json", names)
                self.assertIn("INSTALL_RU.md", names)
                self.assertFalse(any("tests" in n or ".storage" in n or "secrets" in n for n in names))
                self.assertEqual(json.loads(archive.read("release.json"))["commit"], self.item["commit"])
            with zipfile.ZipFile(directory / "machine-monitor-source-v1.4.0.zip") as archive:
                self.assertFalse(any(".env" in n or ".storage" in n or "secrets" in n for n in archive.namelist()))
            for line in (directory / "SHA256SUMS.txt").read_text().splitlines():
                digest, name = line.split("  ")
                self.assertEqual(digest, hashlib.sha256((directory / name).read_bytes()).hexdigest())

    def test_packages_are_reproducible(self):
        with tempfile.TemporaryDirectory() as tmp:
            a = r.build(self.item, self.files, Path(tmp) / "a", b'Notes')
            b = r.build(self.item, dict(reversed(list(self.files.items()))), Path(tmp) / "b", b'Notes')
            self.assertEqual({p.name:p.read_bytes() for p in a.iterdir()}, {p.name:p.read_bytes() for p in b.iterdir()})

    def test_version_schema_and_secret_errors_prevent_build(self):
        for key, value in [(r.COMPONENT + "manifest.json", b'{"version":"1.3.0"}'),
                           (r.COMPONENT + "storage.py", b'data = {"history_schema_version": 3}'),
                           ("README.md", b'github_pat_' + b'A' * 30)]:
            with self.subTest(key=key), self.assertRaises(ValueError):
                r.validate_snapshot(self.item, {**self.files, key:value})

    def test_invalid_catalog_and_zip_paths_are_rejected(self):
        catalog = json.loads((r.ROOT / "releases.json").read_text())
        r.validate_catalog(catalog)
        for alter in (lambda d:d['releases'].append(copy.deepcopy(d['releases'][0])),
                      lambda d:d['releases'][0].update(commit='main'),
                      lambda d:d['releases'][0].update(notes='../private'),
                      lambda d:d['releases'][0].update(latest=True)):
            bad = copy.deepcopy(catalog);alter(bad)
            with self.assertRaises(ValueError):r.validate_catalog(bad)
        for name in ('../private', '/absolute', 'x\\..\\private'):
            with self.assertRaises(ValueError):r.zip_bytes({name:b'x'})

    def test_existing_version_tag_cannot_be_moved(self):
        with patch.object(r, 'api', return_value={'object':{'type':'commit','sha':'f'*40}}) as api:
            with self.assertRaisesRegex(ValueError, 'Refusing to move'):
                r.publish(self.item, Path('.'), 'test-boundary')
            self.assertEqual(api.call_count,1)

    def test_published_assets_are_verified_and_never_replaced(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = r.build(self.item, self.files, Path(tmp), b'Notes')
            assets = [{'name':p.name,'digest':'sha256:'+hashlib.sha256(p.read_bytes()).hexdigest()} for p in directory.iterdir()]
            def api(path, token, *args):
                if path.startswith('git/ref/'):
                    return {'object':{'type':'commit','sha':self.item['commit']}}
                if path.startswith('releases/tags/'):
                    return {'id':7,'draft':False}
                if path.startswith('releases/7/assets'):
                    return assets
                raise AssertionError('Existing release must not mutate')
            with patch.object(r,'api',side_effect=api), patch.object(r,'urlopen') as upload:
                r.publish(self.item,directory,'test-boundary')
                upload.assert_not_called()
                assets[0]['digest']='sha256:wrong'
                with self.assertRaisesRegex(ValueError,'Refusing to replace'):
                    r.publish(self.item,directory,'test-boundary')
                upload.assert_not_called()

    def test_published_incomplete_release_fails_without_upload(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = r.build(self.item,self.files,Path(tmp),b'Notes')
            with patch.object(r,'api',side_effect=[{'object':{'type':'commit','sha':self.item['commit']}},
                    {'id':7,'draft':False},[]]), patch.object(r,'urlopen') as upload:
                with self.assertRaisesRegex(ValueError,'Published release is incomplete'):
                    r.publish(self.item,directory,'test-boundary')
                upload.assert_not_called()


if __name__ == '__main__':
    unittest.main()
