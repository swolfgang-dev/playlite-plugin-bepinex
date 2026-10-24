import importlib.util
import io
import json
from contextlib import nullcontext
from pathlib import Path
import struct
import sys
import tempfile
import unittest
from unittest.mock import Mock,patch
from zipfile import ZipFile
from PyQt6.QtWidgets import QApplication,QWidget
from playlite.providers import IntegrationPlugin

root=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('bepinex_ui_test',root/'__init__.py',submodule_search_locations=[str(root)])
module=importlib.util.module_from_spec(spec);sys.modules[spec.name]=module;spec.loader.exec_module(module)
from bepinex_ui_test.dialog import InstallDialog


class Provider(IntegrationPlugin):
    id='LutrisIntegration';name='Lutris';action_id_field='LutrisId'


class DialogTests(unittest.TestCase):
    def test_il2cpp_install_and_registration_failure_rollback(self):
        for fail,include_manager,bad_digest in ((False,False,False),(False,True,False),(True,True,False),(False,True,True)):
            with self.subTest(fail=fail,include_manager=include_manager,bad_digest=bad_digest),tempfile.TemporaryDirectory() as temporary:
                root=Path(temporary);exe=root/'game.exe'
                data=bytearray(128);data[:2]=b'MZ';struct.pack_into('<I',data,60,64)
                data[64:68]=b'PE\0\0';struct.pack_into('<H',data,68,0x8664);exe.write_bytes(data)
                (root/'GameAssembly.dll').write_bytes(b'original game assembly')
                metadata=root/'game_Data/il2cpp_data/Metadata';metadata.mkdir(parents=True)
                (metadata/'global-metadata.dat').write_bytes(b'original metadata')
                archive=io.BytesIO()
                names=('winhttp.dll','doorstop_config.ini','BepInEx/core/BepInEx.Unity.IL2CPP.dll',
                       'BepInEx/core/BepInEx.Preloader.Core.dll','dotnet/Microsoft.NETCore.App.runtimeconfig.json')
                with ZipFile(archive,'w') as bundle:
                    for name in names:bundle.writestr(name,b'content')
                provider=Provider();provider.detect_running=Mock(return_value=set())
                provider.import_games=Mock(return_value=[dict(Name='Example',LutrisId='12',Executable=str(exe),Prefix='/prefix')])
                provider.launch_configuration=Mock(return_value={'game':{'exe':str(exe)}})
                provider.create_variant=Mock(side_effect=ValueError('registration failed') if fail else None,return_value={'id':13})
                provider.create_variant_transaction=lambda *args,**kwargs:nullcontext(provider.create_variant(*args,**kwargs))
                window=QWidget();window.data=root;window.game_detection=Mock();window.game_detection.status.return_value='Stopped'
                game=dict(Id='existing',Name='Example',PlayActions=[dict(Name='Vanilla',Integration=provider.id,GameId='12')])
                window.games=[game];window.game_providers=[provider];window.focus_added_game=Mock()
                dialog=InstallDialog(window,game,provider)
                self.assertTrue(dialog.add_lutris.isChecked())
                self.assertTrue(dialog.configuration_manager.isChecked())
                self.assertTrue(dialog.configuration_manager.isEnabled())
                self.assertIn('IL2CPP',dialog.runtime_status.text())
                dialog.configuration_manager.setChecked(include_manager)
                dialog.update_runtime()
                self.assertEqual(dialog.configuration_manager.isChecked(),include_manager)
                manager_name='BepInEx/plugins/ConfigurationManager/ConfigurationManager.dll'
                manager_archive=io.BytesIO()
                with ZipFile(manager_archive,'w') as bundle:bundle.writestr(manager_name,b'il2cpp manager')
                pool=Mock();pool.start.side_effect=lambda job:job.run()
                with patch('bepinex_ui_test.dialog.package',return_value=('url','6.0.0-be.789+6cea286',None)) as package, \
                     patch('bepinex_ui_test.dialog.fetch',side_effect=lambda url:manager_archive.getvalue() if url=='manager-url' else archive.getvalue()), \
                     patch('bepinex_ui_test.dialog.configuration_manager_package',return_value=('manager-url','v19.0','sha256:invalid' if bad_digest else None)) as manager, \
                     patch('PyQt6.QtCore.QThreadPool.globalInstance',return_value=pool), \
                     patch('playlite.providers.discover_plugins',return_value={}):
                    dialog.start()
                package.assert_called_once_with('x64','il2cpp')
                if include_manager:manager.assert_called_once_with('il2cpp')
                else:manager.assert_not_called()
                self.assertFalse((root/'BepInEx/config/BepInEx.cfg').exists())
                self.assertEqual((root/'GameAssembly.dll').read_bytes(),b'original game assembly')
                self.assertTrue(dialog.configuration_manager.isEnabled())
                if bad_digest:
                    self.assertIn('checksum mismatch',dialog.status.text())
                    self.assertFalse((root/'winhttp.dll').exists());self.assertFalse((root/'BepInEx').exists())
                    provider.create_variant.assert_not_called()
                elif fail:
                    self.assertFalse((root/'winhttp.dll').exists());self.assertFalse((root/'dotnet').exists())
                    self.assertFalse((root/manager_name).exists())
                    self.assertIn('registration failed',dialog.status.text())
                else:
                    self.assertEqual(window.games[0]['BepInExInstallation']['runtime'],'il2cpp')
                    self.assertTrue((root/'dotnet/Microsoft.NETCore.App.runtimeconfig.json').exists())
                    self.assertEqual((root/manager_name).exists(),include_manager)
                    if include_manager:self.assertIn(manager_name,window.games[0]['BepInExInstallation']['files'])
                dialog.close();window.close()

    def test_installer_controls_belong_to_scrolling_body(self):
        window = QWidget();dialog = InstallDialog(window, dict(Name='Example'), None)
        body = dialog.body_scroll.widget()
        for control in (dialog.executable, dialog.browse_button, dialog.add_lutris,
                        dialog.configuration_manager, dialog.status):
            self.assertTrue(body.isAncestorOf(control))
        self.assertFalse(body.isAncestorOf(dialog.install_button))
        self.assertFalse(body.isAncestorOf(dialog.close_button))
        dialog.close();window.close()

    @classmethod
    def setUpClass(cls):cls.app=QApplication.instance() or QApplication([])
    def test_steam_setup_copies_options_and_opens_linked_action(self):
        from bepinex_ui_test.steam_setup import LAUNCH_OPTIONS,steam_apps,open_properties
        window=QWidget()
        game=dict(Name='Example',PlayActions=[dict(Name='Play Example',Integration='SteamIntegration',GameId='440')])
        dialog=InstallDialog(window,game,None)
        self.assertFalse(dialog.steam_setup.isHidden())
        dialog.copy_steam_button.click()
        self.assertEqual(QApplication.clipboard().text(),LAUNCH_OPTIONS)
        with patch('bepinex_ui_test.dialog.open_properties') as launch:
            dialog.open_steam_button.click();launch.assert_called_once_with('440')
        with patch('bepinex_ui_test.dialog.open_properties',side_effect=OSError('unavailable')):
            dialog.open_steam_button.click()
            self.assertIn('unavailable',dialog.steam_feedback.text())
        self.assertEqual(steam_apps(dict(SteamAppId='0440',PlayActions=game['PlayActions'])),[('440','Game')])
        with patch('bepinex_ui_test.steam_setup.subprocess.Popen') as launch:
            open_properties('440')
            self.assertEqual(launch.call_args.args[0],['xdg-open','steam://gameproperties/440'])
            with self.assertRaises(ValueError):open_properties('440/../../')
            self.assertEqual(launch.call_count,1)
        dialog.close();window.close()

    def test_steam_setup_hidden_without_linked_steam_game(self):
        window=QWidget();dialog=InstallDialog(window,dict(Name='Example'),None)
        self.assertTrue(dialog.steam_setup.isHidden())
        dialog.close();window.close()

    def test_install_creates_modded_action_and_registration_failure_rolls_back(self):
        for fail,include_manager,integrated in ((False,False,True),(False,True,True),(True,True,True),(False,False,False),(False,True,False)):
            with self.subTest(fail=fail,include_manager=include_manager),tempfile.TemporaryDirectory() as temporary:
                root=Path(temporary);exe=root/'game.exe'
                data=bytearray(128);data[:2]=b'MZ';struct.pack_into('<I',data,60,64);data[64:68]=b'PE\0\0';struct.pack_into('<H',data,68,0x8664);exe.write_bytes(data)
                managed=root/'game_Data/Managed';managed.mkdir(parents=True);(managed/'Assembly-CSharp.dll').touch()
                archive=io.BytesIO()
                with ZipFile(archive,'w') as bundle:
                    for name in ('winhttp.dll','doorstop_config.ini','BepInEx/core/BepInEx.Preloader.dll'):bundle.writestr(name,b'content')
                provider=Provider();provider.detect_running=Mock(return_value=set())
                provider.import_games=Mock(return_value=[dict(Name='Example',LutrisId='12',Executable=str(exe),Prefix='/prefix')])
                provider.launch_configuration=Mock(return_value={'game':{'exe':str(exe)},'system':{'env':{'WINEDLLOVERRIDES':'version=n'}}})
                provider.create_variant=Mock(side_effect=ValueError('registration failed') if fail else None,return_value={'id':13})
                provider.create_variant_transaction=lambda *args,**kwargs:nullcontext(provider.create_variant(*args,**kwargs))
                window=QWidget();window.game_detection=Mock();window.game_detection.status.return_value='Stopped'
                game=dict(Id='existing',Name='Example',PlayActions=[dict(Name='Vanilla',Integration=provider.id,GameId='12')])
                window.games=[game];window.data=root;window.game_providers=[provider];window.focus_added_game=Mock()
                dialog=InstallDialog(window,game,provider if integrated else None)
                dialog.add_lutris.setChecked(integrated)
                if not integrated:dialog.executable.setText(str(exe))
                self.assertTrue(dialog.configuration_manager.isChecked())
                dialog.configuration_manager.setChecked(include_manager)
                manager_archive=io.BytesIO()
                with ZipFile(manager_archive,'w') as bundle:
                    bundle.writestr('BepInEx/plugins/ConfigurationManager/ConfigurationManager.dll',b'manager')
                pool=Mock();pool.start.side_effect=lambda job:job.run()
                with patch('bepinex_ui_test.dialog.package',return_value=('url','5.4.23.5',None)),patch('bepinex_ui_test.dialog.configuration_manager_package',return_value=('manager-url','v19.0',None)),patch('bepinex_ui_test.dialog.fetch',side_effect=lambda url: manager_archive.getvalue() if url=='manager-url' else archive.getvalue()),patch('PyQt6.QtCore.QThreadPool.globalInstance',return_value=pool),patch('playlite.providers.discover_plugins',return_value={}):
                    dialog.start()
                if fail:
                    self.assertIn('registration failed',dialog.status.text())
                    self.assertFalse((root/'winhttp.dll').exists());self.assertFalse((root/'BepInEx').exists())
                    self.assertEqual(len(window.games[0]['PlayActions']),1)
                elif not integrated:
                    self.assertEqual(window.games[0]['PlayActions'],game['PlayActions'])
                    provider.create_variant.assert_not_called()
                    self.assertIsNone(window.games[0]['BepInExInstallation']['id'])
                    self.assertTrue((root/'winhttp.dll').exists())
                else:
                    self.assertEqual(len(window.games[0]['PlayActions']),2)
                    self.assertEqual(window.games[0]['PlayActions'][1]['Name'],'Play Example - Modded')
                    self.assertEqual(window.games[0]['PlayActions'][1]['GameId'],'13')
                    self.assertEqual(window.games[0]['PlayActions'][0],game['PlayActions'][0])
                    provider.create_variant.assert_called_once_with('12','Example - Modded','BepInEx',environment={'WINEDLLOVERRIDES':'version=n;winhttp=n,b'},dll_overrides={'winhttp':'n,b'})
                    self.assertTrue((root/'winhttp.dll').exists())
                    self.assertEqual((root/'BepInEx/plugins/ConfigurationManager/ConfigurationManager.dll').exists(),include_manager)
                dialog.close();window.close()
