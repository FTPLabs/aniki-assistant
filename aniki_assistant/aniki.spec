# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec — Аники v2.4
# OPTIM: агрессивные excludes для CUDA/distributed/dynamo → -40% размера и времени сборки
# FIX: hookspath=['hooks'] → перекрывает сломанный hook-webrtcvad.py
# FIX2: _filter_bins обрабатывает 2- и 3-элементные кортежи (PyInstaller 6.x)

import os
from PyInstaller.utils.hooks import collect_all

torch_datas,    torch_bins,    torch_hidden    = collect_all('torch')
torchaudio_datas, torchaudio_bins, torchaudio_hidden = collect_all('torchaudio')
fwhisper_datas, fwhisper_bins, fwhisper_hidden = collect_all('faster_whisper')
ct2_datas,      ct2_bins,      ct2_hidden      = collect_all('ctranslate2')
sd_datas,       sd_bins,       sd_hidden       = collect_all('sounddevice')

# ── Фильтр CUDA DLL — работает с 2-элементными и 3-элементными кортежами ──
# PyInstaller 6.x: collect_all возвращает (dest, src) — 2 элемента
# Некоторые хуки возвращают (dest, src, typecode) — 3 элемента
CUDA_SKIP = (
    'cusparse', 'cublas', 'cudnn', 'curand', 'cufft', 'nccl',
    'nvrtc', 'nvjpeg', 'caffe2', 'fbgemm', 'libtorch_cuda',
)

def _filter_bins(bins):
    result = []
    for item in bins:
        src = item[1]  # src — всегда второй элемент независимо от длины кортежа
        if not any(s in src.lower() for s in CUDA_SKIP):
            result.append(item)
    return result

torch_bins     = _filter_bins(torch_bins)
torchaudio_bins = _filter_bins(torchaudio_bins)

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
    hookspath=['hooks'],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # ── CUDA — сборка CPU-only ──────────────────────────────────
        'torch.cuda',
        'torch.backends.cuda',
        'torch.backends.cudnn',
        'torch.backends.mkldnn',
        'torch.cuda.amp',
        # ── Distributed training ────────────────────────────────────
        'torch.distributed',
        'torch.nn.parallel.distributed',
        'torch.multiprocessing',
        # ── Compiler stack / dynamo / inductor ──────────────────────
        'torch._dynamo',
        'torch._inductor',
        'torch._functorch',
        'torch._decomp',
        'torch.fx',
        # ── ONNX экспорт ────────────────────────────────────────────
        'torch.onnx',
        # ── Профилировщик ───────────────────────────────────────────
        'torch.profiler',
        # ── Quantization ────────────────────────────────────────────
        'torch.ao',
        # ── Тесты / dev инструменты ─────────────────────────────────
        'torch.testing',
        'torch.utils.cpp_extension',
        'caffe2',
        # ── Тяжёлые stdlib-модули, не нужные в десктоп-приложении ──
        'unittest',
        'test',
        'tkinter',
        'matplotlib',
        'scipy',
        'sklearn',
        'pandas',
        'IPython',
        'jedi',
        'setuptools',
        'pkg_resources',
        'distutils',
        'xmlrpc',
        'ftplib',
        'imaplib',
        'poplib',
        'smtplib',
    ],
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
    upx_exclude=[
        'torch*.dll',
        'torchaudio*.dll',
        '*_C.pyd',
        'ct2*.dll',
    ],
    name='Aniki',
)
