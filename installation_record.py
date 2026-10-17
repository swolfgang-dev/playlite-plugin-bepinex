"""Commit installed files, an optional launcher variant, and the library record."""
import copy
from contextlib import nullcontext
import json
from pathlib import Path
from playlite.game_storage import save_game
from playlite.library_storage import library_lock
from playlite.play_actions import actions_for


def commit_installation(data, fallback, providers, install, result, lutris=None, environment=None):
    """Undo this installation if registration or library persistence fails."""
    try:
        transaction = nullcontext({'id': None})
        if result['integrated']:
            create = getattr(lutris, 'create_variant_transaction', None)
            if not callable(create):
                raise ValueError('Update Lutris Integration to 1.1.25 before creating a modded entry.')
            transaction = create(result['source']['LutrisId'], fallback['Name'] + ' - Modded', 'BepInEx',
                                 environment=environment, dll_overrides={'winhttp': 'n,b'})
        with transaction as variant, library_lock(data):
            path = Path(data) / 'library.json'
            games = json.loads(path.read_text()) if path.exists() else [fallback]
            latest = next((game for game in games if game['Id'] == fallback['Id']), None)
            if latest is None:
                raise ValueError('This game was removed during installation.')
            updated = copy.deepcopy(latest)
            actions = copy.deepcopy(updated.get('PlayActions') or []) if 'PlayActions' in updated else actions_for(updated, providers)
            result = dict(result, id=variant['id'])
            if result['integrated']:
                if not any(action.get('Integration') == lutris.id and str(action.get('GameId')) == str(variant['id']) for action in actions):
                    actions.append(dict(Name='Play ' + updated['Name'] + ' - Modded', Integration=lutris.id,
                        GameId=str(variant['id']), Executable=result['executable'],
                        Prefix=result['source'].get('Prefix') or '', Arguments='',
                        InstallDirectory=str(Path(result['executable']).parent)))
                updated['PlayActions'] = actions
            previous = updated.get('BepInExInstallation') or {}
            record = {key: result[key] for key in ('id', 'version', 'sha256', 'executable', 'files')}
            record['runtime'] = result.get('runtime', 'mono')
            if not result['integrated'] and previous.get('executable') == result['executable']:
                record['id'] = previous.get('id')
            updated['BepInExInstallation'] = record
            saved = save_game(Path(data), games, updated)
            return dict(result, games=saved)
    except Exception:
        install.rollback()
        raise
