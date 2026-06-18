# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec — Аники v2.3
# FIX M2: убран устаревший block_cipher (PyInstaller 6.x)
# FIX C2: collect_all встроен прямо в spec — torch/torchaudio/silero/ctranslate2/faster_whisper

import os
from PyInstaller.utils.hooks import collect_all

# ── Сборка torch (Silero TTS работает только если torch полностью включён) ──
torch_datas,    torch_bins,    torch_hidden    = collect_all('torch')
torchaudio_datas, torchaudio_bins, torchaudio_hidden = collect_all('torchaudio')
fwhisper_datas, fwhisper_bins, fwhisper_hidden = collect_all('faster_whisper')
ct2_datas,      ct2_bins,      ct2_hidden      = collect_all('ctranslate2')
sd_datas,       sd_bins,       sd_hidden       = collect_all('sounddevice')

a = Analysis(
    ['main.py'],
    pathex=['.'],
    binaries=[] + torch_bins + torchaudio_bins + fwhisper_bins + ct2_bins + sd_bins,
    datas=[
        ('resources', 'resources'),
        ('data',      'data'),
    ] + torch_datas + torchaudio_datas + fwhisper_datas + ct2_datas + sd_datas,
    hiddenimports=[
        'PyQt6.QtCore',
        'PyQt6.QtWidgets',
        'PyQt6.QtGui',
        'PyQt6.sip',
        'pycaw.pycaw',
        'comtypes',
        'comtypes.client',
        'sounddevice',
        'faster_whisper',
        'faster_whisper.transcribe',
        'ctranslate2',
        'sqlite3',
        'torch',
        'torchaudio',
        'numpy',
        'requests',
        'pyttsx3',
        'pyttsx3.drivers',
        'pyttsx3.drivers.sapi5',
        'win32api',
        'win32com.client',
        'psutil',
        'webrtcvad',
        'pyaudio',
        'PIL',
        'PIL.ImageGrab',
        'urllib.request',
        'urllib.parse',
        'json',
        're',
    ] + torch_hidden + torchaudio_hidden + fwhisper_hidden + ct2_hidden + sd_hidden,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='Aniki',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='resources/aniki.ico',
    version_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='Aniki',
)
