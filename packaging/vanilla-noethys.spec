# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files, collect_submodules

ROOT = Path(SPECPATH).resolve().parent
NOETHYS = ROOT / "noethys"


def collect_runtime_submodules(package):
    excluded_parts = {"test", "tests", "testing"}
    return [
        name
        for name in collect_submodules(package)
        if not excluded_parts.intersection(name.split("."))
    ]


hiddenimports = [
    "wx._xml",
    "wx.richtext",
    "matplotlib.backends.backend_agg",
    "matplotlib.backends.backend_wxagg",
]

for package in (
    "reportlab",
    "sqlalchemy",
    "twisted",
    "lxml",
    "PIL",
    "dateutil",
    "pytz",
    "icalendar",
    "paramiko",
    "comtypes",
    "pyttsx3",
):
    hiddenimports += collect_runtime_submodules(package)


datas = [
    (str(NOETHYS / "Static"), "Static"),
    (str(NOETHYS / "Versions.txt"), "."),
    (str(NOETHYS / "Licence.txt"), "."),
    (str(NOETHYS / "Icone.ico"), "."),
]
datas += collect_data_files("matplotlib")
datas += collect_data_files("pytz")
datas += collect_data_files("reportlab")

analysis = Analysis(
    [str(NOETHYS / "Noethys.py")],
    pathex=[str(ROOT), str(NOETHYS)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["tkinter", "PyQt5", "PyQt6", "PySide2", "PySide6"],
    noarchive=False,
)

pyz = PYZ(analysis.pure)

exe = EXE(
    pyz,
    analysis.scripts,
    [],
    exclude_binaries=True,
    name="Noethys",
    contents_directory=".",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    icon=str(NOETHYS / "Icone.ico"),
)

collect = COLLECT(
    exe,
    analysis.binaries,
    analysis.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="Noethys",
)
