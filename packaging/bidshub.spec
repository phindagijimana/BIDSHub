# PyInstaller spec for the BIDSHub desktop app (phase 3).
#
# The tricky part: Streamlit loads app.py *dynamically* at runtime, so
# PyInstaller's import graph (which starts at desktop/app.py) never sees the
# imports inside app.py and the src.* modules. We therefore:
#   - compile our own packages (src, scripts) as real modules via
#     collect_submodules, and
#   - bundle app.py / assets / .streamlit as data files so the running server
#     can read them from sys._MEIPASS, and
#   - collect_all the data-bearing third-party libs, and copy their metadata
#     (several read importlib.metadata.version at import time).
#
# Build from the repo root:  pyinstaller packaging/bidshub.spec --noconfirm
# Output: dist/BIDSHub/ (onedir) and, on macOS, dist/BIDSHub.app

import sys
from pathlib import Path

from PyInstaller.utils.hooks import collect_all, collect_submodules, copy_metadata

ROOT = Path(SPECPATH).resolve().parent  # SPECPATH = packaging/

datas = []
binaries = []
hiddenimports = []

# --- our app: data Streamlit reads at runtime + modules it imports ----------
datas += [
    (str(ROOT / "app.py"), "."),
    (str(ROOT / ".streamlit"), ".streamlit"),
    (str(ROOT / "assets"), "assets"),
]
hiddenimports += collect_submodules("src")
hiddenimports += collect_submodules("scripts")

# --- heavy / data-bearing third-party libs ---------------------------------
THIRD_PARTY = [
    "streamlit", "bids", "nibabel", "pennsieve", "dandi", "xnat",
    "openneuro", "boto3", "paramiko", "pandas", "numpy", "requests",
]
for pkg in THIRD_PARTY:
    try:
        d, b, h = collect_all(pkg)
        datas += d
        binaries += b
        hiddenimports += h
    except Exception as exc:  # a missing optional lib must not abort the build
        print(f"[spec] collect_all({pkg!r}) skipped: {exc}")

# Distribution metadata some libraries read at import time.
for pkg in ["streamlit", "bids", "nibabel", "dandi", "pennsieve", "numpy",
            "pandas", "pyarrow", "altair", "click"]:
    try:
        datas += copy_metadata(pkg)
    except Exception as exc:
        print(f"[spec] copy_metadata({pkg!r}) skipped: {exc}")

block_cipher = None

a = Analysis(
    [str(ROOT / "desktop" / "app.py")],
    pathex=[str(ROOT)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["tkinter", "pytest"],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="BIDSHub",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,  # phase 3: keep logs visible; phase 4 flips this to windowed
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="BIDSHub",
)

# macOS: wrap the onedir output in an .app bundle (icon added in phase 4).
if sys.platform == "darwin":
    app = BUNDLE(
        coll,
        name="BIDSHub.app",
        icon=None,
        bundle_identifier="org.bidshub.desktop",
        info_plist={
            "CFBundleName": "BIDSHub",
            "CFBundleDisplayName": "BIDSHub",
            "NSHighResolutionCapable": True,
        },
    )
