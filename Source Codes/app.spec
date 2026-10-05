# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller build for "AnyDesk Timer Removal" - optimised for size + startup.
=============================================================================

Why this build is small and starts instantly
--------------------------------------------
* ONEDIR layout - nothing is unpacked into %TEMP% at launch.  A --onefile
  build re-extracts ~40 MB on *every* start; this one just runs.
* Only QtCore / QtGui / QtWidgets survive.  Everything the app never touches
  (QtQuick, Qml, WebEngine, Multimedia, Pdf, Designer, 3D, Sql, Network, ...)
  and the giant Qt payloads that come with them (opengl32sw.dll ~20 MB,
  avcodec-61.dll ~13 MB, d3dcompiler_47.dll ~4 MB) are removed.
* Python bytecode is compiled at optimisation level 2 (docstrings and
  assert statements are stripped).
* UPX is deliberately OFF: UPX-packed executables are far more likely to be
  flagged by antivirus engines, which would hurt trust in the tool.
"""

import os

APP_NAME = "AnyDesk Timer Removal"
ICON = "app.ico"
LOGO = "Cheerful Parrot Hugging Red Logo.png"
LOGO_SMALL = "logo_512.png"


def _prepare_logo():
    """
    Downscale the artwork for the bundle.  The source PNG is 1461x1461 / 1.4 MB;
    at 512x512 it is ~15x smaller, decodes much faster, and is still far more
    resolution than the UI ever needs (the biggest on-screen use is a 150 px
    header image).  If Pillow is unavailable the original file is used as-is.
    """
    try:
        if not os.path.exists(LOGO):
            return LOGO
        stale = (
            not os.path.exists(LOGO_SMALL)
            or os.path.getmtime(LOGO_SMALL) < os.path.getmtime(LOGO)
        )
        if stale:
            from PIL import Image
            im = Image.open(LOGO).convert("RGBA")
            im.thumbnail((512, 512), Image.LANCZOS)
            im.save(LOGO_SMALL, optimize=True)
        return LOGO_SMALL
    except Exception as exc:  # never let artwork stop the build
        print(f"[app.spec] logo downscale skipped ({exc}); using the original")
        return LOGO


LOGO_DATA = _prepare_logo()

# --------------------------------------------------------------------------- #
#  Python / PyQt6 modules that are provably unused.
# --------------------------------------------------------------------------- #
EXCLUDES = [
    # ---- PyQt6 modules we never import ---------------------------------- #
    "PyQt6.QtNetwork", "PyQt6.QtQml", "PyQt6.QtQmlModels", "PyQt6.QtQmlWorkerScript",
    "PyQt6.QtQuick", "PyQt6.QtQuick3D", "PyQt6.QtQuickWidgets", "PyQt6.QtQuickTest",
    "PyQt6.QtMultimedia", "PyQt6.QtMultimediaWidgets", "PyQt6.QtSpatialAudio",
    "PyQt6.QtWebEngineCore", "PyQt6.QtWebEngineWidgets", "PyQt6.QtWebEngineQuick",
    "PyQt6.QtWebChannel", "PyQt6.QtWebSockets", "PyQt6.QtHttpServer",
    "PyQt6.QtSvg", "PyQt6.QtSvgWidgets", "PyQt6.QtPrintSupport",
    "PyQt6.QtOpenGL", "PyQt6.QtOpenGLWidgets",
    "PyQt6.QtSql", "PyQt6.QtTest", "PyQt6.QtDesigner", "PyQt6.QtHelp",
    "PyQt6.QtBluetooth", "PyQt6.QtNfc", "PyQt6.QtPositioning", "PyQt6.QtSensors",
    "PyQt6.QtSerialPort", "PyQt6.QtPdf", "PyQt6.QtPdfWidgets", "PyQt6.QtDBus",
    "PyQt6.QtXml", "PyQt6.QtConcurrent", "PyQt6.QtStateMachine",
    "PyQt6.QtRemoteObjects", "PyQt6.QtTextToSpeech", "PyQt6.QtAxContainer",
    "PyQt6.Qt3DCore", "PyQt6.Qt3DRender", "PyQt6.Qt3DExtras", "PyQt6.Qt3DAnimation",
    "PyQt6.Qt3DInput", "PyQt6.Qt3DLogic", "PyQt6.QtCharts", "PyQt6.QtDataVisualization",
    "PyQt6.QtGraphs", "PyQt6.QtNetworkAuth", "PyQt6.QtScxml", "PyQt6.QtUiTools",
    # ---- other GUI / scientific stacks ---------------------------------- #
    "tkinter", "_tkinter", "turtle", "turtledemo", "idlelib",
    "numpy", "PIL", "Pillow", "cv2", "scipy", "pandas", "matplotlib",
    "IPython", "jupyter", "nbformat", "notebook",
    # ---- standard library we do not use -------------------------------- #
    "unittest", "doctest", "pdb", "pydoc", "pydoc_data", "lib2to3", "test",
    "distutils", "setuptools", "pkg_resources", "pip", "wheel",
    "email", "http", "xmlrpc", "html", "urllib", "xml", "xml.sax",
    "sqlite3", "dbm", "shelve", "bz2", "lzma", "curses", "readline", "rlcompleter",
    "multiprocessing", "asyncio", "concurrent", "socketserver", "ssl", "_ssl",
    "webbrowser", "antigravity", "this",
    # ---- crypto / IO helpers nothing in this app touches --------------- #
    # Dropping hashlib removes libcrypto-3.dll (OpenSSL) - ~5 MB of dead weight.
    "hashlib", "_hashlib", "_md5", "_sha1", "_sha2", "_sha3", "_sha256",
    "_sha512", "_blake2", "_sha512_legacy",
    "select", "selectors", "decimal", "_decimal", "_pydecimal", "unicodedata",
]

a = Analysis(
    ["app.py"],
    pathex=[],
    binaries=[],
    datas=[(LOGO_DATA, ".")],
    hiddenimports=[],
    hookspath=[],
    runtime_hooks=[],
    excludes=EXCLUDES,
    noarchive=False,
    optimize=2,
)
# --------------------------------------------------------------------------- #
#  Safety net: drop any oversized Qt payload a hook may still have pulled in.
#  These are all graphical / multimedia / 3D libraries that a pure QtWidgets
#  application can never load.
# --------------------------------------------------------------------------- #
DEAD_QT_NAMES = {
    "opengl32sw.dll", "d3dcompiler_47.dll", "libegl.dll", "libglesv2.dll",
    "libglslang.dll", "libshadertools.dll", "libvulkan.dll",
    "qt6quick.dll", "qt6qml.dll", "qt6qmlmodels.dll", "qt6qmlworkerscript.dll",
    "qt6quick3d.dll", "qt6quick3dutils.dll", "qt6quickcontrols2.dll",
    "qt6quicktemplates2.dll", "qt6quicklayouts.dll", "qt6quickwidgets.dll",
    "qt6quickdialogs2.dll", "qt6quickshapes.dll", "qt6quickeffects.dll",
    "qt6quickshadertools.dll", "qt6quickparticles.dll", "qt6quicktimeline.dll",
    "qt6quickvectorimage.dll", "qt6quick3dhelpers.dll", "qt6quickeffects.dll",
    "qt6webenginecore.dll", "qt6webenginequick.dll", "qt6webchannel.dll",
    "qt6webview.dll", "qt6websockets.dll", "qt6httpserver.dll",
    "qt6multimedia.dll", "qt6multimediaquick.dll", "qt6multimediawidgets.dll",
    "qt6spatialaudio.dll", "qt6texttospeech.dll", "qt6labsplatform.dll",
    "qt6pdf.dll", "qt6pdfquick.dll", "qt6pdfwidgets.dll",
    "qt6designer.dll", "qt6designercomponents.dll", "qt6help.dll",
    "qt6sql.dll", "qt6test.dll", "qt6network.dll", "qt6bluetooth.dll",
    "qt6nfc.dll", "qt6positioning.dll", "qt6positioningquick.dll",
    "qt6sensors.dll", "qt6sensorsquick.dll", "qt6serialport.dll",
    "qt6svg.dll", "qt6svgwidgets.dll", "qt6xml.dll", "qt6concurrent.dll",
    "qt6opengl.dll", "qt6openglwidgets.dll", "qt6statemachine.dll",
    "qt6statemachineqml.dll", "qt6remoteobjects.dll", "qt6remoteobjectsqml.dll",
    "qt6shadertools.dll", "qt6charts.dll", "qt6datavisualization.dll",
    "qt6graphs.dll", "qt6scxml.dll", "qt6printsupport.dll",
    "avcodec-61.dll", "avformat-61.dll", "avutil-59.dll",
    "swscale-8.dll", "swresample-5.dll",
}

DEAD_PLUGIN_DIRS = {
    "assetimporters", "geometryloaders", "help", "multimedia", "networkinformation",
    "position", "qmllint", "qmlls", "renderers", "sceneparsers", "scxmldatamodel",
    "sensors", "sqldrivers", "texttospeech", "tls", "webview",
}


def _keep_binary(dest):
    low = dest.replace("\\", "/").lower()
    base = low.rsplit("/", 1)[-1]

    if base in DEAD_QT_NAMES:
        return False

    marker = "qt6/plugins/"
    if marker in low:
        rest = low.split(marker, 1)[1]
        if "/" not in rest:
            return False
        if rest.split("/", 1)[0] in DEAD_PLUGIN_DIRS:
            return False
        # Only the icon reader is worth keeping for imageformats; PNG/BMP/XPM
        # are compiled straight into Qt6Gui.
        if rest.startswith("imageformats/") and rest != "imageformats/qico.dll":
            return False
        # Only qwindows.dll is a usable platform plugin on Windows.
        if rest.startswith("platforms/") and rest != "platforms/qwindows.dll":
            return False

    return True


def _keep_data(dest):
    low = dest.replace("\\", "/").lower()
    if low.endswith((".pyi", ".py")):
        return False
    if "/qt6/translations/" in low or "/qt6/resources/" in low or "/qt6/qml/" in low:
        return False
    return True


a.binaries = [b for b in a.binaries if _keep_binary(b[0])]
a.datas = [d for d in a.datas if _keep_data(d[0])]

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name=APP_NAME,
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,            # UPX off on purpose (antivirus false positives)
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=ICON,
    version="version_info.txt",
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name=APP_NAME,
)
