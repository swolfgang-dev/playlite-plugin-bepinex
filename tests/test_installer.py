import io
from pathlib import Path
import struct
import sys
import tempfile
import unittest
from unittest.mock import patch
from zipfile import ZipFile
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from installer import detect,runtime_kind,payload,Installation,overrides,package,executable_candidates,installation_defaults,configuration_manager_package


def executable(machine=0x8664):
    data=bytearray(128);data[:2]=b'MZ';struct.pack_into('<I',data,60,64);data[64:68]=b'PE\0\0';struct.pack_into('<H',data,68,machine);return bytes(data)


class InstallerTests(unittest.TestCase):
    def test_il2cpp_detection_requires_matching_metadata_and_supports_both_architectures(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);exe=root/'game.exe'
            (root/'GameAssembly.dll').touch()
            metadata=root/'game_Data/il2cpp_data/Metadata';metadata.mkdir(parents=True)
            (metadata/'global-metadata.dat').touch()
            for machine,architecture in [(0x8664,'x64'),(0x14c,'x86')]:
                exe.write_bytes(executable(machine))
                self.assertEqual(detect(exe)[1],architecture)
                self.assertEqual(runtime_kind(exe),'il2cpp')
                self.assertEqual(executable_candidates(root),[str(exe)])
            other=root/'other.exe';other.write_bytes(executable())
            with self.assertRaisesRegex(ValueError,'metadata'):detect(other)

    def test_il2cpp_package_uses_latest_matching_official_build(self):
        page=''.join(f'<a href="{url}">download</a>' for url in [
            '/projects/bepinex_be/788/BepInEx-Unity.IL2CPP-win-x64-6.0.0-be.788%2B5b766a3.zip',
            '/projects/bepinex_be/789/BepInEx-Unity.IL2CPP-win-x64-6.0.0-be.789%2B6cea286.zip',
            '/projects/bepinex_be/790/BepInEx-Unity.IL2CPP-win-x86-6.0.0-be.790%2B123abcd.zip',
            'https://example.com/projects/bepinex_be/999/BepInEx-Unity.IL2CPP-win-x64-6.0.0-be.999%2B123abcd.zip'])
        with patch('installer.fetch',return_value=page.encode()):
            url,version,digest=package('x64','il2cpp')
            self.assertTrue(url.startswith('https://builds.bepinex.dev/projects/bepinex_be/789/'))
            self.assertEqual(version,'6.0.0-be.789+6cea286');self.assertIsNone(digest)
        with patch('installer.fetch',return_value=b'<html>No builds</html>'):
            with self.assertRaisesRegex(ValueError,'No official'):package('x64','il2cpp')

    def test_il2cpp_payload_requires_matching_runtime(self):
        archive=io.BytesIO()
        names=('winhttp.dll','doorstop_config.ini','BepInEx/core/BepInEx.Unity.IL2CPP.dll',
               'BepInEx/core/BepInEx.Preloader.Core.dll','dotnet/Microsoft.NETCore.App.runtimeconfig.json')
        with ZipFile(archive,'w') as bundle:
            for name in names:bundle.writestr(name,b'content')
        archive.seek(0);self.assertEqual(set(payload(archive,runtime='il2cpp')),set(names))
        archive.seek(0)
        with self.assertRaises(ValueError):payload(archive)
        archive.seek(0)
        with self.assertRaisesRegex(ValueError,'Unexpected Configuration Manager'):payload(archive,configuration_manager=True,runtime='il2cpp')

    def test_configuration_manager_selects_runtime_and_digest(self):
        import json
        release=dict(tag_name='v19.0',assets=[
            dict(name='BepInEx.ConfigurationManager_BepInEx5_v19.0.zip',browser_download_url='mono-url',digest='sha256:mono'),
            dict(name='BepInEx.ConfigurationManager_IL2CPP_v19.0.zip',browser_download_url='il2cpp-url',digest='sha256:il2cpp')])
        with patch('installer.fetch',return_value=json.dumps(release).encode()):
            self.assertEqual(configuration_manager_package(),('mono-url','v19.0','sha256:mono'))
            self.assertEqual(configuration_manager_package('il2cpp'),('il2cpp-url','v19.0','sha256:il2cpp'))
            with self.assertRaisesRegex(ValueError,'Unsupported Unity runtime'):configuration_manager_package('other')
        release['assets'].pop()
        with patch('installer.fetch',return_value=json.dumps(release).encode()):
            with self.assertRaisesRegex(ValueError,'IL2CPP Configuration Manager package is unavailable'):configuration_manager_package('il2cpp')

    def test_configuration_manager_rate_limit_fallback_keeps_runtime(self):
        from urllib.error import HTTPError
        from unittest.mock import MagicMock
        response=MagicMock()
        response.__enter__.return_value.geturl.return_value='https://github.com/BepInEx/BepInEx.ConfigurationManager/releases/tag/v19.0'
        with patch('installer.fetch',side_effect=HTTPError('api',403,'Rate limited',{},None)),patch('installer.urllib.request.urlopen',return_value=response):
            url,version,digest=configuration_manager_package('il2cpp')
        self.assertTrue(url.endswith('/v19.0/BepInEx.ConfigurationManager_IL2CPP_v19.0.zip'))
        self.assertEqual(version,'v19.0');self.assertIsNone(digest)

    def test_configuration_manager_payload_accepts_plugins_only_for_both_runtimes(self):
        for runtime in ('mono','il2cpp'):
            for extra in (None,'BepInEx/core/unexpected.dll','../escape'):
                with self.subTest(runtime=runtime,extra=extra):
                    archive=io.BytesIO()
                    with ZipFile(archive,'w') as bundle:
                        bundle.writestr('BepInEx/plugins/ConfigurationManager/ConfigurationManager.dll',b'manager')
                        bundle.writestr('BepInEx/plugins/ConfigurationManager/LICENSE',b'license')
                        if extra:bundle.writestr(extra,b'bad')
                    archive.seek(0)
                    if extra:
                        with self.assertRaises(ValueError):payload(archive,configuration_manager=True,runtime=runtime)
                    else:
                        self.assertEqual(len(payload(archive,configuration_manager=True,runtime=runtime)),2)

    def test_manager_protection_default_preserves_existing_config_and_rolls_back(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);name='BepInEx/config/BepInEx.cfg'
            files=installation_defaults(root,{'winhttp.dll':b'dll'})
            install=Installation(root,files);install.apply()
            self.assertIn(b'HideManagerGameObject = true',(root/name).read_bytes())
            install.rollback();self.assertFalse((root/name).exists())
            (root/name).parent.mkdir(parents=True);(root/name).write_bytes(b'[Chainloader]\nHideManagerGameObject = false\n')
            files=installation_defaults(root,{'winhttp.dll':b'dll'})
            self.assertNotIn(name,files)
            Installation(root,files).apply()
            self.assertIn(b'false',(root/name).read_bytes())

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
