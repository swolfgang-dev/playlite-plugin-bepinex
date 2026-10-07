from pathlib import Path
from PyQt6.QtWidgets import QMessageBox
from playlite.providers import GenericPlugin,discover_plugins
from playlite.play_actions import actions_for


class Plugin(GenericPlugin):
    def game_actions(self,window,game):
        lutris=discover_plugins().get('LutrisIntegration')
        if not lutris:return []
        if not any(action.get('Integration')==lutris.id for action in actions_for(game,[lutris])):return []
        return [('Install BepInEx and add modded launch…',lambda:self.install(window,game,lutris))]

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
