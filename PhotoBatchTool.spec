# PyInstaller spec for the Photo Batch Tool.
# Build with:  pyinstaller PhotoBatchTool.spec
from pathlib import Path

from PyInstaller.utils.hooks import collect_all

datas = []
binaries = []
hiddenimports = []

for pkg in ("rembg", "onnxruntime"):
    pkg_datas, pkg_binaries, pkg_hiddenimports = collect_all(pkg)
    datas += pkg_datas
    binaries += pkg_binaries
    hiddenimports += pkg_hiddenimports

# Bundle the U2Net model if the build environment has already fetched it
# (see .github/workflows/build-windows-exe.yml), so end users never need
# their own internet access for the first-run model download.
_bundled_model = Path("models/u2net.onnx")
if _bundled_model.exists():
    datas += [(str(_bundled_model), "models")]

a = Analysis(
    ["main.py"],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
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
    name="PhotoBatchTool",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
)
