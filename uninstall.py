"""Transactional removal of a verified BepInEx package."""
import hashlib
from pathlib import Path, PurePosixPath
import shutil
import tempfile


class Removal:
    def __init__(self, root, hashes, keep_data=True):
        self.root = Path(root).resolve(strict=True)
        self.hashes = hashes
        self.keep_data = keep_data
        self.moves = []
        self.backup = None

    def apply(self):
        targets = []
        for name, digest in self.hashes.items():
            relative = PurePosixPath(name)
            if relative.is_absolute() or '..' in relative.parts or '\\' in name:
                raise ValueError('Unsafe BepInEx installation record.')
            if self.keep_data and relative.parts[:2] in [('BepInEx', 'plugins'), ('BepInEx', 'config'), ('BepInEx', 'patchers')]:
                continue
            target = self.root / name
            if target.is_symlink() or any(p.is_symlink() for p in target.parents if p != self.root and self.root in p.parents):
                raise ValueError('Refusing a symlinked BepInEx path.')
            if target.exists():
                if not target.is_file() or hashlib.sha256(target.read_bytes()).hexdigest() != digest:
                    # Settings such as doorstop_config.ini may have been edited.
                    if name != 'doorstop_config.ini':
                        raise ValueError('BepInEx file has changed; uninstall stopped: ' + name)
                targets.append(target)
        data = self.root / 'BepInEx'
        if not self.keep_data and data.exists():
            if data.is_symlink() or not data.is_dir():
                raise ValueError('Unsafe BepInEx user data directory.')
            targets = [p for p in targets if not p.is_relative_to(data)] + [data]
        self.backup = Path(tempfile.mkdtemp(prefix='.playlite-bepinex-uninstall-', dir=self.root))
        try:
            for index, target in enumerate(targets):
                destination = self.backup / str(index)
                target.rename(destination)
                self.moves.append((target, destination))
        except Exception:
            self.rollback()
            raise

    def rollback(self):
        for target, backup in reversed(self.moves):
            backup.rename(target)
        self.moves.clear()
        if self.backup:
            shutil.rmtree(self.backup)
            self.backup = None

    def finish(self):
        if self.backup:
            shutil.rmtree(self.backup)
            self.backup = None
        for directory in sorted((self.root / 'BepInEx').rglob('*'), key=lambda p: len(p.parts), reverse=True):
            if directory.is_dir() and not directory.is_symlink():
                try: directory.rmdir()
                except OSError: pass
