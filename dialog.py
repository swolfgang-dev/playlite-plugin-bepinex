import hashlib
import json
from pathlib import Path
import tempfile
from PyQt6.QtCore import QObject,QRunnable,QThreadPool,pyqtSignal
from PyQt6.QtWidgets import QDialog,QVBoxLayout,QLabel,QComboBox,QPushButton,QHBoxLayout
from playlite.play_actions import actions_for
from .installer import detect,package,fetch,payload,Installation,overrides


class Signals(QObject):
    progress=pyqtSignal(str)
    finished=pyqtSignal(object,str)


class Job(QRunnable):
    def __init__(self,operation):
        super().__init__();self.signals=Signals();self.operation=operation
    def run(self):
        try:result=self.operation(self.signals.progress.emit)
        except Exception as error:self.signals.finished.emit(None,str(error))
        else:self.signals.finished.emit(result,'')


class InstallDialog(QDialog):
    def __init__(self,window,game,lutris):
        super().__init__(window)
        self.window=window;self.game=game;self.lutris=lutris;self.job=None
        self.setWindowTitle('Install BepInEx');self.resize(600,260)
        layout=QVBoxLayout(self)
        explanation=QLabel('Install stable BepInEx 5 for a Windows Unity Mono game. A separate “[Game] - Modded” Lutris entry will use the same runner and prefix, with BepInEx loading enabled. Existing game files will never be overwritten.')
        explanation.setWordWrap(True);layout.addWidget(explanation)
        self.source=QComboBox()
        ids={str(action.get('GameId')) for action in actions_for(game,[lutris]) if action.get('Integration')==lutris.id}
        for item in lutris.import_games():
            if str(item.get('LutrisId')) not in ids:continue
            try:
                executable,architecture=detect(item.get('Executable') or '')
                configuration=lutris.launch_configuration(item['LutrisId'])
                if str(configuration.get('playlite_variant','')).endswith(':BepInEx'):continue
            except (ValueError,OSError):continue
            self.source.addItem(f'{item["Name"]} — {architecture}',item)
        layout.addWidget(self.source)
        self.status=QLabel('Choose the source Lutris entry.');self.status.setWordWrap(True);layout.addWidget(self.status)
        footer=QHBoxLayout();footer.addStretch()
        self.install_button=QPushButton('Install and add modded launch');self.install_button.clicked.connect(self.start)
        self.close_button=QPushButton('Close');self.close_button.clicked.connect(self.reject)
        footer.addWidget(self.install_button);footer.addWidget(self.close_button);layout.addLayout(footer)
        if not self.source.count():
            self.status.setText('No supported Windows Unity Mono Lutris action was found for this game. IL2CPP and native Linux games are not supported.')
            self.install_button.setEnabled(False)

    def reject(self):
        if self.job is None:super().reject()

    def start(self):
        if self.job:return
        source=self.source.currentData()
        if not source:return
        if self.window.game_detection.status(self.game['Id']) in ('Launching','Running') or self.game['Id'] in self.lutris.detect_running([self.game]):
            self.status.setText('Close the game before installing BepInEx.');return
        self.install_button.setEnabled(False);self.close_button.setEnabled(False);self.source.setEnabled(False)
        def operation(progress):
            executable,architecture=detect(source['Executable'])
            configuration=self.lutris.launch_configuration(source['LutrisId'])
            if Path(configuration['game']['exe']).resolve()!=executable:raise ValueError('The source executable changed. Reopen this installer.')
            progress('Finding the stable BepInEx release…')
            url,version,expected=package(architecture)
            progress('Downloading BepInEx '+version+'…');archive=fetch(url)
            digest=hashlib.sha256(archive).hexdigest()
            if expected and expected!='sha256:'+digest:raise ValueError('BepInEx package checksum mismatch.')
            with tempfile.TemporaryDirectory(prefix='playlite-bepinex-') as temporary:
                path=Path(temporary)/'package.zip';path.write_bytes(archive)
                files=payload(path)
            install=Installation(executable.parent,files)
            progress('Installing BepInEx beside the game executable…');install.apply()
            try:
                progress('Creating the modded Lutris entry…')
                environment=configuration.get('system',{}).get('env',{}) or {}
                result=self.lutris.create_variant(source['LutrisId'],self.game['Name']+' - Modded','BepInEx',
                    environment={'WINEDLLOVERRIDES':overrides(environment.get('WINEDLLOVERRIDES',''))},
                    dll_overrides={'winhttp':'n,b'})
            except Exception:install.rollback();raise
            return dict(id=result['id'],version=version,sha256=digest,executable=str(executable),source=source)
        self.job=Job(operation)
        self.job.signals.progress.connect(self.status.setText)
        self.job.signals.finished.connect(self.finished_install)
        QThreadPool.globalInstance().start(self.job)

    def finished_install(self,result,error):
        self.job=None;self.close_button.setEnabled(True);self.source.setEnabled(True)
        if error:
            self.status.setText(error);self.install_button.setEnabled(True);return
        try:
            import copy
            from playlite.editor import save_game
            latest=next(game for game in self.window.games if game['Id']==self.game['Id'])
            updated=copy.deepcopy(latest)
            actions=copy.deepcopy(updated['PlayActions'] or []) if 'PlayActions' in updated else actions_for(updated,self.window.game_providers)
            if not any(action.get('Integration')==self.lutris.id and str(action.get('GameId'))==str(result['id']) for action in actions):
                actions.append(dict(Name=updated['Name']+' - Modded',Integration=self.lutris.id,GameId=str(result['id']),
                    Executable=result['executable'],Prefix=result['source'].get('Prefix') or '',Arguments='',InstallDirectory=str(Path(result['executable']).parent)))
            updated['PlayActions']=actions
            updated['BepInExInstallation']={key:result[key] for key in ('id','version','sha256','executable')}
            self.window.games=save_game(self.window.data,self.window.games,updated)
            self.window.focus_added_game(updated['Id'])
        except Exception as error:
            self.status.setText('BepInEx and Lutris entry installed, but the Playlite action could not be saved: '+str(error))
            self.install_button.setEnabled(True);return
        self.status.setText('Installed BepInEx '+result['version']+'. Select “[Game] - Modded” from the Play dropdown.')
