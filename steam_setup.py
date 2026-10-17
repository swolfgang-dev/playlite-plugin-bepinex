"""Guide Steam users without rewriting Steam's saved launch options."""
import subprocess
from playlite.desktop import host_environment

LAUNCH_OPTIONS = 'WINEDLLOVERRIDES="winhttp=n,b" %command%'


def steam_apps(game):
    candidates = [(game.get('SteamAppId'), game.get('Name', 'Game'))]
    candidates.extend((action.get('GameId'), action.get('Name', 'Steam'))
                      for action in game.get('PlayActions', []) or []
                      if action.get('Integration') == 'SteamIntegration')
    result = []
    for identity, name in candidates:
        identity = str(identity or '')
        if identity.isascii() and identity.isdigit() and int(identity) > 0:
            identity = str(int(identity))
            if not any(app_id == identity for app_id, _ in result):
                result.append((identity, name))
    return result


def open_properties(app_id):
    identity = str(app_id or '')
    if not identity.isascii() or not identity.isdigit() or int(identity) < 1:
        raise ValueError('A positive numeric Steam app ID is required.')
    environment = host_environment()
    return subprocess.Popen(['xdg-open', 'steam://gameproperties/' + str(int(identity))],
                            env=environment, start_new_session=True,
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

