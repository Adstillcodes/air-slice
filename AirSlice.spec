# PyInstaller build spec — one self-contained app folder, no Python needed.
# Build:  pyinstaller AirSlice.spec
# Output: dist/AirSlice/  (dist/AirSlice.app on macOS)
import sys

from PyInstaller.utils.hooks import collect_all

# mediapipe ships .tflite models and .binarypb graphs that must be bundled
datas = [("assets/sounds", "assets/sounds")]
binaries = []
hiddenimports = []
for pkg in ("mediapipe",):
    d, b, h = collect_all(pkg)
    datas += d
    binaries += b
    hiddenimports += h

a = Analysis(
    ["launcher.py"],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="AirSlice",
    debug=False,
    strip=False,
    upx=False,
    console=False,  # no terminal window behind the game
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="AirSlice",
)

if sys.platform == "darwin":
    app = BUNDLE(
        coll,
        name="AirSlice.app",
        icon=None,
        bundle_identifier="org.ieee-ras.air-slice",
        info_plist={
            "NSCameraUsageDescription": "Air Slice tracks your hand with the webcam to play.",
            "NSHighResolutionCapable": True,
        },
    )
