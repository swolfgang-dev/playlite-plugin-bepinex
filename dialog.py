import hashlib
import json
from pathlib import Path
import tempfile
from PyQt6.QtCore import QObject,QRunnable,QThreadPool,pyqtSignal
from PyQt6.QtWidgets import QApplication,QWidget,QDialog,QVBoxLayout,QLabel,QComboBox,QPushButton,QHBoxLayout,QCheckBox,QLineEdit,QLayout,QSizePolicy
from playlite.play_actions import actions_for
from .installer import detect,package,fetch,payload,Installation,overrides,configuration_manager_package
from .steam_setup import LAUNCH_OPTIONS,steam_apps,open_properties


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
        self.setWindowTitle('Install BepInEx');self.resize(800,600)
        layout=QVBoxLayout(self)
        layout.setSizeConstraint(QLayout.SizeConstraint.SetMinimumSize)
        explanation=QLabel('Install stable BepInEx 5 beside the game executable. Optionally copy an existing Lutris entry to “[Game] - Modded” and add the BepInEx DLL override to the copy. Existing game files will never be overwritten.')
        explanation.setWordWrap(True);layout.addWidget(explanation)
        self.source=QComboBox()
        available=lutris and all(callable(getattr(lutris,name,None)) for name in ('create_variant','launch_configuration'))
        ids={str(action.get('GameId')) for action in actions_for(game,[lutris]) if action.get('Integration')==lutris.id} if available else set()
        for item in lutris.import_games() if available else []:
            if str(item.get('LutrisId')) not in ids:continue
            try:
                executable,architecture=detect(item.get('Executable') or '')
                configuration=lutris.launch_configuration(item['LutrisId'])
                if str(configuration.get('playlite_variant','')).endswith(':BepInEx'):continue
            except (ValueError,OSError):continue
            self.source.addItem(f'{item["Name"]} — {architecture}',item)
        self.add_lutris=QCheckBox('Add Lutris integration (copy the existing entry)')
        self.add_lutris.setEnabled(bool(self.source.count()))
        self.add_lutris.setChecked(bool(self.source.count()))
        if not self.source.count():self.add_lutris.setToolTip('Requires Lutris Integration 1.1.17 or newer and an existing supported Lutris action.')
        layout.addWidget(self.add_lutris);layout.addWidget(self.source)
        executable=game.get('Executable') or game.get('BepInExInstallation',{}).get('executable') or ''
        if not executable:
            executable=next((action.get('Executable') for action in game.get('PlayActions',[]) or [] if action.get('Executable')),'')
        self.executable=QLineEdit(executable)
        self.browse_button=QPushButton('Browse executable…');self.browse_button.clicked.connect(self.browse_executable)
        executable_row=QHBoxLayout();executable_row.addWidget(self.executable);executable_row.addWidget(self.browse_button);layout.addLayout(executable_row)
        self.add_lutris.toggled.connect(self.update_controls)
        self.configuration_manager=QCheckBox('Include Configuration Manager (in-game settings, F1)')
        self.configuration_manager.setChecked(True);layout.addWidget(self.configuration_manager)
        self.steam_setup=QWidget();steam_layout=QVBoxLayout(self.steam_setup)
        steam_layout.setSizeConstraint(QLayout.SizeConstraint.SetMinimumSize)
        self.steam_setup.setSizePolicy(QSizePolicy.Policy.Preferred,QSizePolicy.Policy.Minimum)
        steam_layout.setContentsMargins(0,0,0,0)
        steam_help=QLabel('For Steam / Proton, after installation open Steam Properties → General → Launch Options and add the winhttp override shown below. If launch options already exist, preserve them and add the override before %command%; do not add a second %command%. This enables BepInEx for all Steam launches of this game.')
        self.steam_help=steam_help
        steam_help.setWordWrap(True);steam_layout.addWidget(steam_help)
        self.steam_options=QLineEdit(LAUNCH_OPTIONS);self.steam_options.setReadOnly(True);steam_layout.addWidget(self.steam_options)
        self.steam_game=QComboBox()
        for app_id,name in steam_apps(game):self.steam_game.addItem(f'{name} — {app_id}',app_id)
        self.steam_game.setVisible(self.steam_game.count()>1);steam_layout.addWidget(self.steam_game)
        steam_buttons=QHBoxLayout()
        self.copy_steam_button=QPushButton('Copy launch options');self.copy_steam_button.clicked.connect(self.copy_steam_options)
        self.open_steam_button=QPushButton('Open Steam Properties');self.open_steam_button.clicked.connect(self.open_steam_properties)
        steam_buttons.addWidget(self.copy_steam_button);steam_buttons.addWidget(self.open_steam_button);steam_buttons.addStretch()
        steam_layout.addLayout(steam_buttons)
        self.steam_feedback=QLabel();self.steam_feedback.setWordWrap(True);steam_layout.addWidget(self.steam_feedback)
        layout.addWidget(self.steam_setup)
        self.status=QLabel('Choose the game executable, or enable Lutris integration to copy an existing entry.');self.status.setWordWrap(True);layout.addWidget(self.status)
        footer=QHBoxLayout();footer.addStretch()
        self.install_button=QPushButton('Install');self.install_button.clicked.connect(self.start)
        self.close_button=QPushButton('Close');self.close_button.clicked.connect(self.reject)
        footer.addWidget(self.install_button);footer.addWidget(self.close_button);layout.addLayout(footer)
        self.update_controls()
        self.ensurePolished()
        for control in (self.steam_options,self.copy_steam_button,self.open_steam_button):
            control.ensurePolished();control.setMinimumHeight(control.sizeHint().height())
        self.fit_steam_help()
        self.adjustSize()

    def fit_steam_help(self):
        if hasattr(self,'steam_help'):
            width=max(200,self.width()-self.layout().contentsMargins().left()-self.layout().contentsMargins().right())
            self.steam_help.setMinimumHeight(self.steam_help.heightForWidth(width))

    def resizeEvent(self,event):
        super().resizeEvent(event)
        self.fit_steam_help()

    def update_controls(self):
        integrated=self.add_lutris.isChecked()
        self.source.setVisible(integrated)
        self.executable.setEnabled(not integrated and self.job is None)
        self.browse_button.setEnabled(not integrated and self.job is None)
        self.steam_setup.setVisible(not integrated and bool(self.steam_game.count()))

    def copy_steam_options(self):
        QApplication.clipboard().setText(LAUNCH_OPTIONS)
        self.steam_feedback.setText('Copied. Paste into Steam → Properties → General → Launch Options, preserving any existing options.')

    def open_steam_properties(self):
        try:open_properties(self.steam_game.currentData())
        except (ValueError,OSError) as error:self.steam_feedback.setText('Could not open Steam Properties: '+str(error))
        else:self.steam_feedback.setText('In Steam Properties, select General → Launch Options.')

    def browse_executable(self):
        from playlite.lifecycle import choose_file
        path,_=choose_file(self,'Choose the game executable',self.executable.text() or self.game.get('InstallDirectory',''),'Windows executables (*.exe)')
        if path:self.executable.setText(path)

    def reject(self):
        if self.job is None:super().reject()

    def start(self):
        if self.job:return
        integrated=self.add_lutris.isChecked()
        source=self.source.currentData() if integrated else dict(Executable=self.executable.text().strip())
        if not source:return
        if self.window.game_detection.status(self.game['Id']) in ('Launching','Running') or (self.lutris and self.game['Id'] in self.lutris.detect_running([self.game])):
            self.status.setText('Close the game before installing BepInEx.');return
        self.install_button.setEnabled(False);self.close_button.setEnabled(False);self.source.setEnabled(False)
        self.add_lutris.setEnabled(False);self.executable.setEnabled(False);self.browse_button.setEnabled(False)
        include_manager=self.configuration_manager.isChecked()
        self.configuration_manager.setEnabled(False)
        def operation(progress):
            executable,architecture=detect(source['Executable'])
            configuration=self.lutris.launch_configuration(source['LutrisId']) if integrated else {}
            if integrated and Path(configuration['game']['exe']).resolve()!=executable:raise ValueError('The source executable changed. Reopen this installer.')
            progress('Finding the stable BepInEx release…')
            url,version,expected=package(architecture)
            progress('Downloading BepInEx '+version+'…');archive=fetch(url)
            digest=hashlib.sha256(archive).hexdigest()
            if expected and expected!='sha256:'+digest:raise ValueError('BepInEx package checksum mismatch.')
            with tempfile.TemporaryDirectory(prefix='playlite-bepinex-') as temporary:
                path=Path(temporary)/'package.zip';path.write_bytes(archive)
                files=payload(path)
            if include_manager:
                progress('Finding Configuration Manager for BepInEx 5…')
                manager_url,manager_version,manager_digest=configuration_manager_package()
                progress('Downloading Configuration Manager '+manager_version+'…')
                manager_archive=fetch(manager_url)
                if manager_digest and manager_digest!='sha256:'+hashlib.sha256(manager_archive).hexdigest():raise ValueError('Configuration Manager checksum mismatch.')
                with tempfile.TemporaryDirectory(prefix='playlite-bepinex-manager-') as temporary:
                    path=Path(temporary)/'manager.zip';path.write_bytes(manager_archive)
                    files.update(payload(path,configuration_manager=True))
            install=Installation(executable.parent,files)
            progress('Installing BepInEx beside the game executable…');install.apply()
            try:
                result={'id':None}
                if integrated:progress('Copying the existing Lutris entry and adding the DLL override…')
                environment=configuration.get('system',{}).get('env',{}) or {}
                if integrated:result=self.lutris.create_variant(source['LutrisId'],self.game['Name']+' - Modded','BepInEx',
                    environment={'WINEDLLOVERRIDES':overrides(environment.get('WINEDLLOVERRIDES',''))},
                    dll_overrides={'winhttp':'n,b'})
            except Exception:install.rollback();raise
            return dict(id=result['id'],version=version,sha256=digest,executable=str(executable),source=source,integrated=integrated,files={name:hashlib.sha256(content).hexdigest() for name,content in files.items()})
        self.job=Job(operation)
        self.job.signals.progress.connect(self.status.setText)
        self.job.signals.finished.connect(self.finished_install)
        QThreadPool.globalInstance().start(self.job)

    def finished_install(self,result,error):
        self.add_lutris.setEnabled(bool(self.source.count()))
        self.configuration_manager.setEnabled(True)
        self.job=None;self.close_button.setEnabled(True);self.source.setEnabled(True)
        self.update_controls()
        if error:
            self.status.setText(error);self.install_button.setEnabled(True);return
        try:
            import copy
            from playlite.editor import save_game
            latest=next(game for game in self.window.games if game['Id']==self.game['Id'])
            updated=copy.deepcopy(latest)
            actions=copy.deepcopy(updated['PlayActions'] or []) if 'PlayActions' in updated else actions_for(updated,self.window.game_providers)
            if result['integrated'] and not any(action.get('Integration')==self.lutris.id and str(action.get('GameId'))==str(result['id']) for action in actions):
                actions.append(dict(Name='Play '+updated['Name']+' - Modded',Integration=self.lutris.id,GameId=str(result['id']),
                    Executable=result['executable'],Prefix=result['source'].get('Prefix') or '',Arguments='',InstallDirectory=str(Path(result['executable']).parent)))
            if result['integrated']:updated['PlayActions']=actions
            previous=updated.get('BepInExInstallation',{})
            updated['BepInExInstallation']={key:result[key] for key in ('id','version','sha256','executable','files')}
            if not result['integrated'] and previous.get('executable')==result['executable']:
                updated['BepInExInstallation']['id']=previous.get('id')
            self.window.games=save_game(self.window.data,self.window.games,updated)
            self.window.focus_added_game(updated['Id'])
        except Exception as error:
            self.status.setText('BepInEx installed, but its Playlite installation record could not be saved: '+str(error))
            self.install_button.setEnabled(True);return
        self.status.setText('Installed BepInEx '+result['version']+('. Select “Play [Game] - Modded” from the Play dropdown.' if result['integrated'] else '. Files installed; launcher configuration was not changed.'))
