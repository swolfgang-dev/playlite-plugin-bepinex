import hashlib
from pathlib import Path
import tempfile
import unittest
from uninstall import Removal


class UninstallTests(unittest.TestCase):
    def test_keep_user_data_and_rollback(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary)
            files={'winhttp.dll':b'runtime','BepInEx/core/runtime.dll':b'core','BepInEx/plugins/mod.dll':b'mod','BepInEx/config/mod.cfg':b'settings','BepInEx/patchers/patch.dll':b'patch'}
            for name,content in files.items():
                path=root/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(content)
            hashes={name:hashlib.sha256(content).hexdigest() for name,content in files.items()}
            removal=Removal(root,hashes,True);removal.apply()
            self.assertFalse((root/'winhttp.dll').exists())
            for name in list(files)[2:]:self.assertTrue((root/name).exists())
            removal.rollback()
            for name,content in files.items():self.assertEqual((root/name).read_bytes(),content)
            removal=Removal(root,hashes,True);removal.apply();removal.finish()
            self.assertTrue((root/'BepInEx/plugins/mod.dll').exists())

    def test_remove_data_does_not_remove_game(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);(root/'BepInEx/plugins').mkdir(parents=True)
            (root/'BepInEx/plugins/mod.dll').write_bytes(b'mod');(root/'game.exe').touch()
            removal=Removal(root,{},False);removal.apply();removal.finish()
            self.assertFalse((root/'BepInEx').exists());self.assertTrue((root/'game.exe').exists())

    def test_changed_runtime_stops_before_removing_files(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);(root/'winhttp.dll').write_bytes(b'changed')
            with self.assertRaises(ValueError):Removal(root,{'winhttp.dll':hashlib.sha256(b'original').hexdigest()}).apply()
            self.assertEqual((root/'winhttp.dll').read_bytes(),b'changed')
