"""Stable Windows Unity Mono package detection and non-overwriting extraction."""
import hashlib
import json
from pathlib import Path,PurePosixPath
import re
import stat
import struct
import urllib.request
from urllib.error import HTTPError
from urllib.parse import urlparse
from zipfile import ZipFile

REPOSITORY='BepInEx/BepInEx'


def detect(executable):
    path=Path(executable).expanduser().resolve(strict=True)
    if not path.is_file() or path.suffix.lower()!='.exe':raise ValueError('Select a Windows game executable.')
    data=path.with_name(path.stem+'_Data')
    if (path.parent/'GameAssembly.dll').exists():raise ValueError('IL2CPP is not supported by this stable Unity Mono installer.')
    if not (data/'Managed'/'Assembly-CSharp.dll').is_file():raise ValueError('No Unity Mono managed assemblies were found beside this executable.')
    with path.open('rb') as stream:
        if stream.read(2)!=b'MZ':raise ValueError('The game is not a Windows executable.')
        stream.seek(60);header=stream.read(4)
        if len(header)!=4:raise ValueError('Truncated Windows executable.')
        offset=struct.unpack('<I',header)[0]
        stream.seek(offset)
        if stream.read(4)!=b'PE\0\0':raise ValueError('Invalid Windows executable header.')
        header=stream.read(2)
        if len(header)!=2:raise ValueError('Truncated Windows executable.')
        machine=struct.unpack('<H',header)[0]
    if machine not in (0x14c,0x8664):raise ValueError('Only Windows x86 and x64 games are supported.')
    return path,'x64' if machine==0x8664 else 'x86'


def fetch(url):
    request=urllib.request.Request(url,headers={'User-Agent':'Playlite-BepInEx'})
    with urllib.request.urlopen(request,timeout=60) as response:
        data=response.read(64*1024*1024+1)
    if len(data)>64*1024*1024:raise ValueError('The download exceeds the package size limit.')
    return data


def package(architecture):
    try:
        release=json.loads(fetch(f'https://api.github.com/repos/{REPOSITORY}/releases/latest'))
        if release.get('draft') or release.get('prerelease'):raise ValueError('A stable BepInEx release is unavailable.')
        version=release['tag_name'].removeprefix('v')
        if not re.fullmatch(r'5\.[0-9.]+',version):raise ValueError('The latest release is not supported BepInEx 5.')
        name=f'BepInEx_win_{architecture}_{version}.zip'
        asset=next((asset for asset in release['assets'] if asset['name']==name),None)
        if asset is None:raise ValueError('The matching Windows BepInEx package is unavailable.')
        return asset['browser_download_url'],version,asset.get('digest')
    except HTTPError as error:
        if error.code not in (403,429):raise
        with urllib.request.urlopen(f'https://github.com/{REPOSITORY}/releases/latest',timeout=60) as response:
            path=urlparse(response.geturl()).path
        match=re.fullmatch(r'/BepInEx/BepInEx/releases/tag/v(5\.[0-9.]+)',path)
        if not match:raise ValueError('Could not resolve a stable BepInEx 5 release.')
        version=match[1]
        return f'https://github.com/{REPOSITORY}/releases/download/v{version}/BepInEx_win_{architecture}_{version}.zip',version,None


def payload(archive):
    with ZipFile(archive) as bundle:
        entries=bundle.infolist()
        if len(entries)>2000 or sum(item.file_size for item in entries)>200*1024*1024:raise ValueError('BepInEx archive is too large.')
        files={};seen=set()
        for item in entries:
            path=PurePosixPath(item.filename)
            if not path.parts or path.is_absolute() or '..' in path.parts or '\\' in item.filename or stat.S_ISLNK(item.external_attr>>16):raise ValueError('Unsafe archive path.')
            key=path.as_posix().casefold()
            if key in seen:raise ValueError('Duplicate archive path.')
            seen.add(key)
            if not item.is_dir():files[path.as_posix()]=bundle.read(item)
        required=('winhttp.dll','doorstop_config.ini','BepInEx/core/BepInEx.Preloader.dll')
        if not all(name in files for name in required):raise ValueError('This is not a Windows BepInEx 5 package.')
        return files


class Installation:
    def __init__(self,root,files):
        self.root=Path(root);self.files=files;self.created=[];self.directories=[]
    def apply(self):
        # Check the complete payload before writing anything.
        for name,content in self.files.items():
            target=self.root/name
            if target.is_symlink() or any(parent.is_symlink() for parent in target.parents if parent!=self.root and self.root in parent.parents):raise ValueError('Refusing a symlinked installation path.')
            if target.exists() and (not target.is_file() or target.read_bytes()!=content):raise ValueError('Existing file would be overwritten: '+name)
        try:
            for name,content in self.files.items():
                target=self.root/name
                if target.exists():continue
                missing=[];parent=target.parent
                while not parent.exists():missing.append(parent);parent=parent.parent
                for parent in reversed(missing):parent.mkdir();self.directories.append(parent)
                with target.open('xb') as stream:
                    self.created.append(target);stream.write(content)
        except Exception:self.rollback();raise
    def rollback(self):
        for path in reversed(self.created):path.unlink(missing_ok=True)
        for path in reversed(self.directories):
            try:path.rmdir()
            except OSError:pass


def overrides(existing):
    parts=[]
    for item in (existing or '').split(';'):
        if not item:continue
        names,separator,value=item.partition('=')
        if not separator:raise ValueError('The source DLL overrides are malformed.')
        remaining=[name for name in names.split(',') if name.strip().casefold()!='winhttp']
        if remaining:parts.append(','.join(remaining)+'='+value)
    return ';'.join([*parts,'winhttp=n,b'])
