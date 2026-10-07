"""Guide Steam users without rewriting Steam's saved launch options."""
import os
import pwd
import subprocess

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
    environment = os.environ.copy()
    if environment.get('PLAYLITE_PROFILE') == 'repo':
        environment['HOME'] = environment.get('PLAYLITE_HOST_HOME') or pwd.getpwuid(os.getuid()).pw_dir
        for key in ('XDG_DATA_HOME', 'XDG_CONFIG_HOME', 'XDG_CACHE_HOME', 'XDG_STATE_HOME'):
            value = environment.get('PLAYLITE_HOST_' + key)
            if value:
                environment[key] = value
            else:
                environment.pop(key, None)
    return subprocess.Popen(['xdg-open', 'steam://gameproperties/' + str(int(identity))],
                            env=environment, start_new_session=True,
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def show_instructions(parent, game):
    from PyQt6.QtWidgets import (QApplication,QDialog,QVBoxLayout,QLabel,QLineEdit,
                                QComboBox,QPushButton,QHBoxLayout)
    from playlite.lifecycle import run_dialog
    apps = steam_apps(game)
    if not apps:
        return
    dialog = QDialog(parent)
    dialog.setWindowTitle('BepInEx — Steam launch options')
    dialog.resize(720,400)
    layout = QVBoxLayout(dialog)
    help_text = QLabel('In Steam, open Properties → General → Launch Options and add the winhttp override below. Preserve existing options and put the override before the existing %command%; do not add a second %command%. This enables BepInEx for every Steam launch of this game. After uninstalling BepInEx, remove only its winhttp=n,b override and keep your other options.')
    help_text.setWordWrap(True)
    layout.addWidget(help_text)
    options = QLineEdit(LAUNCH_OPTIONS)
    options.setReadOnly(True)
    layout.addWidget(options)
    games = QComboBox()
    for app_id,name in apps:
        games.addItem(f'{name} — {app_id}',app_id)
    games.setVisible(len(apps)>1)
    layout.addWidget(games)
    feedback = QLabel()
    feedback.setWordWrap(True)
    buttons = QHBoxLayout()
    copy = QPushButton('Copy launch options')
    def copy_options():
        QApplication.clipboard().setText(LAUNCH_OPTIONS)
        feedback.setText('Copied. Paste into Steam → Properties → General → Launch Options.')
    copy.clicked.connect(copy_options)
    properties = QPushButton('Open Steam Properties')
    def open_steam():
        try:open_properties(games.currentData())
        except (ValueError,OSError) as error:feedback.setText('Could not open Steam Properties: '+str(error))
        else:feedback.setText('In Steam Properties, select General → Launch Options.')
    properties.clicked.connect(open_steam)
    close = QPushButton('Close')
    close.clicked.connect(dialog.accept)
    buttons.addWidget(copy);buttons.addWidget(properties);buttons.addStretch();buttons.addWidget(close)
    layout.addLayout(buttons)
    layout.addWidget(feedback)
    run_dialog(dialog)
