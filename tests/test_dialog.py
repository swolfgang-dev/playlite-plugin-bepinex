import importlib.util
import io
import json
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
    @classmethod
    def setUpClass(cls):cls.app=QApplication.instance() or QApplication([])
    def test_install_creates_modded_action_and_registration_failure_rolls_back(self):
        for fail in (False,True):
            with self.subTest(fail=fail),tempfile.TemporaryDirectory() as temporary:
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
                window=QWidget();window.game_detection=Mock();window.game_detection.status.return_value='Stopped'
                game=dict(Id='existing',Name='Example',PlayActions=[dict(Name='Vanilla',Integration=provider.id,GameId='12')])
                window.games=[game];window.data=root;window.game_providers=[provider];window.focus_added_game=Mock()
                dialog=InstallDialog(window,game,provider)
                pool=Mock();pool.start.side_effect=lambda job:job.run()
                with patch('bepinex_ui_test.dialog.package',return_value=('url','5.4.23.5',None)),patch('bepinex_ui_test.dialog.fetch',return_value=archive.getvalue()),patch('PyQt6.QtCore.QThreadPool.globalInstance',return_value=pool),patch('playlite.providers.discover_plugins',return_value={}):
                    dialog.start()
                if fail:
                    self.assertIn('registration failed',dialog.status.text())
                    self.assertFalse((root/'winhttp.dll').exists());self.assertFalse((root/'BepInEx').exists())
                    self.assertEqual(len(window.games[0]['PlayActions']),1)
                else:
                    self.assertEqual(len(window.games[0]['PlayActions']),2)
                    self.assertEqual(window.games[0]['PlayActions'][1]['Name'],'Play Example - Modded')
                    self.assertEqual(window.games[0]['PlayActions'][1]['GameId'],'13')
                    self.assertEqual(window.games[0]['PlayActions'][0],game['PlayActions'][0])
                    provider.create_variant.assert_called_once_with('12','Example - Modded','BepInEx',environment={'WINEDLLOVERRIDES':'version=n;winhttp=n,b'},dll_overrides={'winhttp':'n,b'})
                    self.assertTrue((root/'winhttp.dll').exists())
                dialog.close();window.close()
