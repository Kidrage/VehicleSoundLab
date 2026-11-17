"""Non-RT identity of catalog files, including the legacy F2 runtime inputs.

All other current catalog model loaders read beneath voices/. The three F2
files below are the explicit exception in fine_idle_drive_v1/models.c. Compiled
constants belong to the DLL identity rather than this runtime-file inventory.
"""
from copy import deepcopy
import hashlib
import json
from pathlib import Path

SCHEMA = 'vsl.catalog-assets/1'
LEGACY_INPUTS = (
    'experiments/modal_idle_v1/F2_fixed_idle.msource',
    'experiments/modal_texture_v1/F2_amplitude.mtexture',
    'experiments/spectral_texture_v1/F2_fine_static.sfir',
)


def digest(manifest):
    return hashlib.sha256(json.dumps(manifest, ensure_ascii=False, sort_keys=True,
        separators=(',', ':'), allow_nan=False).encode('utf-8')).hexdigest()


def inventory(repo):
    repo = Path(repo)
    paths = {p.relative_to(repo).as_posix(): p for p in (repo/'voices').rglob('*') if p.is_file()}
    if not paths:
        raise RuntimeError('声源参数库为空')
    for name in LEGACY_INPUTS:
        paths[name] = repo/name
    files = {}
    for name,path in sorted(paths.items()):
        if not path.is_file():
            raise RuntimeError('声源目录缺少参数文件：'+name)
        with path.open('rb') as stream:
            files[name] = hashlib.file_digest(stream, 'sha256').hexdigest()
    manifest = dict(schema=SCHEMA, files=files)
    return digest(manifest), manifest


def live(bridge):
    if bridge.abi() >= 9 and inventory(bridge.repo)[0] != bridge.catalog_assets_sha256:
        raise RuntimeError('声源目录参数已变化，请重开控制窗口并载入对应版本')


def attach(bridge, value):
    if bridge.abi() >= 9:
        live(bridge)
        value['catalog_assets_sha256'] = bridge.catalog_assets_sha256
        value['catalog_assets'] = deepcopy(bridge.catalog_assets)
    return value


def verify(bridge, value):
    if bridge.abi() >= 9:
        live(bridge)
        if value.get('catalog_assets') != bridge.catalog_assets or value.get('catalog_assets_sha256') != bridge.catalog_assets_sha256:
            raise ValueError('行程或配方的声源目录参数不匹配，请使用对应冻结版本')
