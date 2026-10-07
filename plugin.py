from pathlib import Path
from playlite.providers import GenericPlugin,discover_plugins
from playlite.play_actions import actions_for


class Plugin(GenericPlugin):
    def game_actions(self,window,game):
        folder_actions=[('Open BepInEx plugins folder',lambda:self.open_plugins_folder(window,game))] if self.plugins_folder(game) else []
        lutris=discover_plugins().get('LutrisIntegration')
        if not lutris:return folder_actions
        if not any(action.get('Integration')==lutris.id for action in actions_for(game,[lutris])):return folder_actions
        actions=[('Install BepInEx and add modded launch…',lambda:self.install(window,game,lutris))]
        if game.get('BepInExInstallation'):
            actions.append(('Uninstall BepInEx…',lambda:self.uninstall(window,game,lutris)))
        return actions+folder_actions

    @staticmethod
    def plugins_folder(game):
        executables=[game.get('BepInExInstallation',{}).get('executable'),game.get('Executable')]
        executables.extend(action.get('Executable') for action in game.get('PlayActions',[]) or [])
        for value in executables:
            if not value:continue
            executable=Path(value).expanduser()
            if not executable.is_absolute():continue
            root=executable.parent
            folder=root/'BepInEx'/'plugins'
            installed=(root/'winhttp.dll').is_file() and (root/'BepInEx/core/BepInEx.Preloader.dll').is_file()
            if folder.is_dir() or installed:return folder
        return None

    def open_plugins_folder(self,window,game):
        from playlite.desktop import open_folder
        from playlite.lifecycle import show_warning
        try:
            folder=self.plugins_folder(game)
            if folder is None:
                raise ValueError('BepInEx is not installed and its plugins folder does not exist.')
            folder.mkdir(parents=True,exist_ok=True)
            open_folder(folder)
        except (KeyError,ValueError,OSError) as error:
            show_warning(window,'BepInEx plugins folder',str(error))

    def install(self,window,game,lutris):
        from .dialog import InstallDialog
        from playlite.lifecycle import run_dialog,show_warning
        try:
            if not all(callable(getattr(lutris,name,None)) for name in ('create_variant','launch_configuration')):
                raise ValueError('Update Lutris Integration to a version supporting modded launch variants.')
            if window.game_detection.status(game['Id']) in ('Launching','Running') or game['Id'] in lutris.detect_running([game]):
                raise ValueError('Close the game before installing BepInEx.')
            run_dialog(InstallDialog(window,game,lutris))
        except (ValueError,OSError) as error:show_warning(window,'BepInEx Installer',str(error))

    def uninstall(self,window,game,lutris):
        import copy,hashlib,tempfile
        from PyQt6.QtWidgets import QDialog,QVBoxLayout,QLabel,QCheckBox,QDialogButtonBox
        from playlite.lifecycle import run_dialog,show_warning
        from playlite.editor import save_game
        from .installer import detect,fetch,payload
        from .uninstall import Removal
        try:
            if window.game_detection.status(game['Id']) in ('Launching','Running') or game['Id'] in lutris.detect_running([game]):
                raise ValueError('Close the game before uninstalling BepInEx.')
            dialog=QDialog(window);dialog.setWindowTitle('Uninstall BepInEx')
            layout=QVBoxLayout(dialog)
            layout.addWidget(QLabel('Remove BepInEx and its modded launch entry? Game files and the Wine prefix are kept.'))
            keep=QCheckBox('Keep user data (plugins, configuration, and patchers)');keep.setChecked(True)
            layout.addWidget(keep)
            buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel)
            confirm=buttons.addButton('Uninstall',QDialogButtonBox.ButtonRole.AcceptRole)
            confirm.clicked.connect(dialog.accept);buttons.rejected.connect(dialog.reject);layout.addWidget(buttons)
            if run_dialog(dialog)!=QDialog.DialogCode.Accepted:return
            latest=next(item for item in window.games if item['Id']==game['Id'])
            record=latest['BepInExInstallation'];executable=Path(record['executable'])
            hashes=record.get('files')
            if not hashes:
                # Older installations did not record individual file hashes.
                architecture=detect(executable)[1]
                version=record['version']
                import re
                if not re.fullmatch(r'5\.\d+\.\d+(?:\.\d+)?',version):raise ValueError('Invalid installed BepInEx version.')
                url=f'https://github.com/BepInEx/BepInEx/releases/download/v{version}/BepInEx_win_{architecture}_{version}.zip'
                archive=fetch(url)
                if hashlib.sha256(archive).hexdigest()!=record['sha256']:raise ValueError('Installed package checksum mismatch.')
                with tempfile.TemporaryDirectory() as temporary:
                    path=Path(temporary)/'package.zip';path.write_bytes(archive)
                    hashes={name:hashlib.sha256(content).hexdigest() for name,content in payload(path).items()}
            removal=Removal(executable.parent,hashes,keep.isChecked());backup=None
            removal.apply()
            try:
                backup=lutris.delete_entry(dict(latest,PlayActions=[dict(Integration=lutris.id,GameId=str(record['id']))]))
                updated=copy.deepcopy(latest)
                updated['PlayActions']=[action for action in actions_for(latest,window.game_providers)
                    if not (action.get('Integration')==lutris.id and str(action.get('GameId'))==str(record['id']))]
                updated.pop('BepInExInstallation',None)
                window.games=save_game(window.data,window.games,updated)
            except Exception:
                if backup is not None:lutris.restore_deleted_entry(backup)
                removal.rollback();raise
            removal.finish();window.focus_added_game(game['Id'])
        except (ValueError,OSError,KeyError) as error:show_warning(window,'BepInEx uninstall',str(error))
