from pathlib import Path
import sys


project_root = Path(SPECPATH)
icon = project_root / "assets" / "icons" / (
    "tapestries-muck.icns" if sys.platform == "darwin" else "tapestries-muck.ico"
)

a = Analysis(
    [str(project_root / "run.py")],
    pathex=[str(project_root)],
    binaries=[],
    datas=[(str(project_root / "assets"), "assets")],
    hiddenimports=[],
    hookspath=[],
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="TapestriesMuck",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    icon=str(icon),
)

if sys.platform == "darwin":
    app = BUNDLE(
        exe,
        name="TapestriesMuck.app",
        icon=str(icon),
        bundle_identifier="com.tapestries.muckclient",
        info_plist={
            "CFBundleDisplayName": "TapestriesMuck",
            "CFBundleName": "TapestriesMuck",
            "CFBundleShortVersionString": "0.3.1",
            "CFBundleVersion": "0.3.1",
            "NSHighResolutionCapable": True,
        },
    )
