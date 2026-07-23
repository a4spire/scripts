# PyInstaller spec for the Photo Batch Tool.
# Build with:  pyinstaller PhotoBatchTool.spec
from PyInstaller.utils.hooks import collect_all, copy_metadata

datas = []
binaries = []
hiddenimports = []

for pkg in ("rembg", "onnxruntime", "cv2", "tkinterdnd2"):
    pkg_datas, pkg_binaries, pkg_hiddenimports = collect_all(pkg)
    datas += pkg_datas
    binaries += pkg_binaries
    hiddenimports += pkg_hiddenimports

# rembg imports pymatting at module load time (for alpha matting), and pymatting
# reads its own version via importlib.metadata at import time. collect_all("rembg")
# only bundles rembg's own dist-info, not this transitive dependency's -- without
# it, `import rembg` fails in the frozen EXE with "No package metadata was found
# for pymatting", taking the whole rembg import down with it.
datas += copy_metadata("pymatting")

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
