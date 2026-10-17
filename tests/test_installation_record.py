import copy
from contextlib import contextmanager
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch
import test_dialog  # Initializes the isolated plugin package.
from bepinex_ui_test.installation_record import commit_installation
from bepinex_ui_test.installer import Installation


class InstallationRecordTests(unittest.TestCase):
    def test_failed_library_write_rolls_back_files_and_launcher_variant(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            game = {'Id': 'one', 'Name': 'Example', 'PlayActions': []}
            (root / 'library.json').write_text(json.dumps([game]))
            before = (root / 'library.json').read_bytes()
            installation = Installation(root, {'winhttp.dll': b'new runtime'})
            installation.apply()
            rolled_back = []
            @contextmanager
            def variant(*args, **kwargs):
                try:
                    yield {'id': 12}
                except Exception:
                    rolled_back.append(True)
                    raise
            provider = Mock(id='LutrisIntegration', create_variant_transaction=variant)
            result = dict(integrated=True, source={'LutrisId': '1'}, version='5', sha256='hash',
                          executable=str(root / 'game.exe'), files={})
            with patch('bepinex_ui_test.installation_record.save_game', side_effect=OSError('disk full')):
                with self.assertRaisesRegex(OSError, 'disk full'):
                    commit_installation(root, game, [], installation, result, provider)
            self.assertEqual(rolled_back, [True])
            self.assertFalse((root / 'winhttp.dll').exists())
            self.assertEqual((root / 'library.json').read_bytes(), before)

    def test_latest_metadata_is_used_and_removed_game_is_not_resurrected(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            old = {'Id': 'one', 'Name': 'Original'}
            latest = dict(old, Name='Renamed', Playtime=120)
            path = root / 'library.json'
            path.write_text(json.dumps([latest]))
            result = dict(integrated=False, source={}, version='5', sha256='hash',
                          executable=str(root / 'game.exe'), files={}, runtime='mono')
            install = Mock()
            with patch('playlite.providers.discover_plugins', return_value={}):
                saved = commit_installation(root, old, [], install, result)['games'][0]
            self.assertEqual(saved['Name'], 'Renamed')
            self.assertEqual(saved['Playtime'], 120)
            install.rollback.assert_not_called()
            path.write_text('[]')
            with self.assertRaisesRegex(ValueError, 'removed'):
                commit_installation(root, old, [], install, result)
            install.rollback.assert_called_once()
            self.assertEqual(path.read_text(), '[]')

    def test_rollback_preserves_later_edits_to_installed_files(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            operation = Installation(root, {'winhttp.dll': b'installed'})
            operation.apply()
            (root / 'winhttp.dll').write_bytes(b'later edit')
            operation.rollback()
            self.assertEqual((root / 'winhttp.dll').read_bytes(), b'later edit')
