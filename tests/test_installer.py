import io
from pathlib import Path
import struct
import sys
import tempfile
import unittest
from unittest.mock import patch
from zipfile import ZipFile
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from installer import detect,payload,Installation,overrides,package,executable_candidates


def executable(machine=0x8664):
    data=bytearray(128);data[:2]=b'MZ';struct.pack_into('<I',data,60,64);data[64:68]=b'PE\0\0';struct.pack_into('<H',data,68,machine);return bytes(data)


class InstallerTests(unittest.TestCase):
    def test_finds_only_supported_local_mono_executables(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);game=root/'game';game.mkdir()
            for folder,name in [(game,'First'),(game/'nested','Second'),(root/'outside','External')]:
                folder.mkdir(parents=True,exist_ok=True);(folder/(name+'.exe')).write_bytes(executable())
                managed=folder/(name+'_Data')/'Managed';managed.mkdir(parents=True);(managed/'Assembly-CSharp.dll').touch()
            (game/'external').symlink_to(root/'outside',target_is_directory=True)
            (game/'launcher.exe').write_bytes(executable())
            self.assertEqual(executable_candidates(game),[str(game/'First.exe'),str(game/'nested/Second.exe')])
            (game/'nested/GameAssembly.dll').touch()
            self.assertEqual(executable_candidates(game),[str(game/'First.exe')])

    def test_detects_mono_architecture_and_rejects_il2cpp(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);exe=root/'game.exe';exe.write_bytes(executable())
            managed=root/'game_Data/Managed';managed.mkdir(parents=True);(managed/'Assembly-CSharp.dll').touch()
            self.assertEqual(detect(exe)[1],'x64')
            exe.write_bytes(executable(0x14c));self.assertEqual(detect(exe)[1],'x86')
            (root/'GameAssembly.dll').touch()
            with self.assertRaisesRegex(ValueError,'IL2CPP'):detect(exe)

    def test_rejects_non_unity_and_invalid_executable(self):
        with tempfile.TemporaryDirectory() as temporary:
            exe=Path(temporary)/'game.exe';exe.write_bytes(b'bad')
            with self.assertRaises(ValueError):detect(exe)

    def test_archive_validation_rejects_traversal_and_wrong_package(self):
        for name in ('../escape','/absolute','normal.txt'):
            data=io.BytesIO()
            with ZipFile(data,'w') as archive:archive.writestr(name,b'content')
            data.seek(0)
            with self.assertRaises(ValueError):payload(data)

    def test_payload_retains_license(self):
        data=io.BytesIO()
        with ZipFile(data,'w') as archive:
            for name in ('winhttp.dll','doorstop_config.ini','BepInEx/core/BepInEx.Preloader.dll','BepInEx/core/LICENSE'):archive.writestr(name,b'content')
        data.seek(0);self.assertIn('BepInEx/core/LICENSE',payload(data))

    def test_install_reuses_identical_files_and_rollback_keeps_existing(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);existing=root/'winhttp.dll';existing.write_bytes(b'same')
            operation=Installation(root,{'winhttp.dll':b'same','BepInEx/core/lib.dll':b'new'})
            operation.apply();self.assertTrue((root/'BepInEx/core/lib.dll').exists())
            operation.rollback();self.assertFalse((root/'BepInEx').exists());self.assertEqual(existing.read_bytes(),b'same')

    def test_conflict_preflight_writes_nothing(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);(root/'winhttp.dll').write_bytes(b'other loader')
            with self.assertRaises(ValueError):Installation(root,{'new.txt':b'new','winhttp.dll':b'replacement'}).apply()
            self.assertFalse((root/'new.txt').exists())
            self.assertEqual((root/'winhttp.dll').read_bytes(),b'other loader')

    def test_symlink_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);(root/'BepInEx').symlink_to(root)
            with self.assertRaises(ValueError):Installation(root,{'BepInEx/lib.dll':b'new'}).apply()
            self.assertFalse((root/'lib.dll').exists())

    def test_override_preserves_other_libraries(self):
        self.assertEqual(overrides('dinput8,winhttp=b;version=n'),'dinput8=b;version=n;winhttp=n,b')

    def test_package_selects_architecture_and_digest(self):
        import json
        release=dict(tag_name='v5.4.23.5',assets=[dict(name='BepInEx_win_x64_5.4.23.5.zip',browser_download_url='url',digest='sha256:hash')])
        with patch('installer.fetch',return_value=json.dumps(release).encode()):
            self.assertEqual(package('x64'),('url','5.4.23.5','sha256:hash'))
            with self.assertRaises(ValueError):package('x86')
