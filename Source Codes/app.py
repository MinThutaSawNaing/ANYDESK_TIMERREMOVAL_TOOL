#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AnyDesk Timer Removal
=====================

A friendly PyQt6 front-end for the steps performed by ``AnyDesk.bat``.
Resetting AnyDesk's configuration clears the free-session timer, which is why
the tool is called "AnyDesk Timer Removal".

What it does (same as the batch file):
    1. Stop the machine-wide "AnyDesk" service (if present).
    2. Close every AnyDesk / AnyDeskMSI process.
    3. Delete the AnyDesk configuration files:
         * %ProgramData%\\AnyDesk\\service.conf
         * %ProgramData%\\AnyDesk\\system.conf
         * %AppData%\\AnyDesk\\system.conf
         * %AppData%\\AnyDesk\\user.conf   (optional - brand new ID)
    4. Locate and restart AnyDesk.exe.

Design goals
------------
* Runs as Administrator automatically (UAC prompt on start).
* Never opens a console / "cmd" window - the app relaunches itself through
  ``pythonw.exe`` and every helper process is spawned hidden.
* Simple by default: one big button. Everything else hides behind "Advanced".
* Every window shows the parrot logo.

Artwork is loaded from the PNG next to this script:
    "Cheerful Parrot Hugging Red Logo.png"

Run with:
    pythonw app.py          (recommended - no console window)
    python  app.py          (auto-relaunches console-less)

Command line flags:
    --no-elevate            do not try to become Administrator
    --relaunched            internal flag, set on the elevated re-launch
"""

from __future__ import annotations

import ctypes
import os
import subprocess
import sys
import time
import winreg
from pathlib import Path

from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QIcon, QPixmap
from PyQt6.QtWidgets import (
    QApplication,
    QCheckBox,
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

# --------------------------------------------------------------------------- #
#  Constants
# --------------------------------------------------------------------------- #
APP_NAME = "AnyDesk Timer Removal"
LOGO_FILE_NAME = "Cheerful Parrot Hugging Red Logo.png"
# The packaged build ships a downscaled copy of the artwork so the bundle stays
# small and the logo decodes faster; running from source still uses the
# original full-resolution PNG.
LOGO_COMPACT_NAME = "logo_512.png"
SERVICE_NAME = "AnyDesk"
PROCESS_NAMES = ("AnyDesk.exe", "AnyDeskMSI.exe")

RELAUNCH_FLAG = "--relaunched"
NO_ELEVATE_FLAG = "--no-elevate"

# Windows process creation flag (literal so this never raises on other systems)
CREATE_NO_WINDOW = 0x08000000

# Default set of operations - mirrors AnyDesk.bat exactly.
DEFAULT_OPTIONS = {
    "stop_service": True,
    "kill_processes": True,
    "reset_machine": True,
    "reset_user": True,
    "wipe_id": False,        # destructive - off by default, like the .bat
    "start_anydesk": True,
}


# --------------------------------------------------------------------------- #
#  Path / environment helpers
# --------------------------------------------------------------------------- #
def app_dir() -> Path:
    """Folder that holds app.py (or the frozen executable) and the artwork."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(os.path.abspath(sys.argv[0])).resolve().parent


def _script_dir() -> Path:
    """
    Folder that holds this source file - or, when frozen by PyInstaller, the
    folder that holds the .exe (``__file__`` would point into the temporary
    extraction directory instead).
    """
    if getattr(sys, "frozen", False):
        return app_dir()
    try:
        return Path(os.path.abspath(__file__)).resolve().parent
    except NameError:  # pragma: no cover - __file__ always exists here
        return app_dir()


def resource_path(name: str) -> Path:
    """Resolve a bundled resource, honouring PyInstaller's ``_MEIPASS``."""
    base = getattr(sys, "_MEIPASS", None)
    if base:
        candidate = Path(base) / name
        if candidate.is_file():
            return candidate
    for folder in (_script_dir(), app_dir()):
        candidate = folder / name
        if candidate.is_file():
            return candidate
# --------------------------------------------------------------------------- #
#  Elevation / "no console window" helpers
# --------------------------------------------------------------------------- #
def is_admin() -> bool:
    """True when the current process has administrator privileges."""
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def console_attached() -> bool:
    """True when this process is attached to a console (i.e. a cmd window)."""
    try:
        return ctypes.windll.kernel32.GetConsoleWindow() != 0
    except Exception:
        return False


def pythonw_executable() -> str:
    """
    Return ``pythonw.exe`` when we are running from ``python.exe`` so the
    re-launched copy never shows a console window.
    """
    exe = Path(sys.executable)
    if exe.name.lower() == "python.exe":
        candidate = exe.with_name("pythonw.exe")
        if candidate.is_file():
            return str(candidate)
    return str(exe)


def launch_elevated_consoleless() -> bool:
    """
    Re-start this app through UAC ("runas") using pythonw.exe so it runs as
    Administrator *and* without any console window.  Returns True when the new
    instance was handed over successfully.
    """
    keep = [a for a in sys.argv[1:] if a not in (RELAUNCH_FLAG, NO_ELEVATE_FLAG)]

    if getattr(sys, "frozen", False):
        exe = sys.executable
        args = keep
    else:
        exe = pythonw_executable()
        args = [os.path.abspath(sys.argv[0]), *keep]

    args.append(RELAUNCH_FLAG)
    params = subprocess.list2cmdline(args)

    try:
        # ShellExecuteW returns a value > 32 when the launch succeeded.
        result = ctypes.windll.shell32.ShellExecuteW(
            None, "runas", exe, params, str(app_dir()), 1
        )
        return result > 32
    except Exception:
        return False


def _hidden_startupinfo():
    """A STARTUPINFO that keeps any child process completely invisible."""
    try:
        si = subprocess.STARTUPINFO()
        si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        si.wShowWindow = subprocess.SW_HIDE
        return si
    except Exception:  # pragma: no cover - non-Windows fallback
        return None


def run_cmd(args) -> tuple[int, str]:
    """Run an external command with no visible window; return (code, output)."""
    args = [str(a) for a in args]

    kwargs = {
        "capture_output": True,
        "text": True,
        "stdin": subprocess.DEVNULL,
        "creationflags": CREATE_NO_WINDOW,
    }
    si = _hidden_startupinfo()
    if si is not None:
        kwargs["startupinfo"] = si

    try:
        proc = subprocess.run(args, **kwargs)
        output = (proc.stdout or "") + (proc.stderr or "")
        return proc.returncode, output.strip()
    except FileNotFoundError:
        return -1, f"command not found: {args[0]}"
    except Exception as exc:  # defensive - never let the worker die silently
        return -1, str(exc)


def find_anydesk_exe() -> str | None:
    """
    Locate AnyDesk.exe exactly like the batch file:
      1. every Program Files folder,
      2. the "App Paths" registry key (any custom install path),
      3. the portable copy sitting next to this script.
    """
    candidates: list[Path] = []

    for var in ("ProgramFiles", "ProgramFiles(x86)", "ProgramW6432"):
        base = os.environ.get(var)
        if base:
            candidates.append(Path(base) / "AnyDesk" / "AnyDesk.exe")

    try:
        key_path = r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\AnyDesk.exe"
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, key_path) as key:
            value, _ = winreg.QueryValueEx(key, "")
            if value:
                candidates.append(Path(value))
    except OSError:
        pass

    candidates.append(_script_dir() / "AnyDesk.exe")

    for path in candidates:
        try:
            if path.is_file():
                return str(path)
        except OSError:
            continue
    return None


_logo_cache: dict[int, QPixmap] = {}


def logo_source() -> Path:
    """Prefer the compact build-time artwork, fall back to the original PNG."""
    compact = resource_path(LOGO_COMPACT_NAME)
    if compact.is_file():
        return compact
    return resource_path(LOGO_FILE_NAME)


def logo_pixmap(size: int) -> QPixmap:
    """
    The parrot logo scaled to ``size``.  The source image is decoded once and
    the result cached - the original artwork is large, and the app asks for the
    logo several times (app icon, window icons, headers, dialogs).
    """
    cached = _logo_cache.get(size)
    if cached is not None:
        return cached

    path = logo_source()
    pix = QPixmap(str(path)) if path.is_file() else QPixmap()
    if pix.isNull():
        pix = QPixmap(size, size)
        pix.fill(QColor("#d32f2f"))
    else:
        pix = pix.scaled(
            size,
            size,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
    _logo_cache[size] = pix
    return pix
# --------------------------------------------------------------------------- #
#  Dialogs - every window carries the parrot logo
# --------------------------------------------------------------------------- #
class LogoDialog(QDialog):
    """
    Base dialog that always shows the parrot logo, both in the title bar and
    inside the window body.  Sub-classes (or the ``show_dialog`` helper) just
    add a heading, some widgets and buttons.
    """

    def __init__(self, parent=None, title: str = APP_NAME) -> None:
        super().__init__(parent)
        self.choice: str | None = None

        self.setWindowTitle(title)
        icon = QIcon(logo_pixmap(256))
        if not icon.isNull():
            self.setWindowIcon(icon)
        self.setModal(True)
        self.setMinimumWidth(430)

        self._root = QVBoxLayout(self)
        self._root.setContentsMargins(20, 20, 20, 18)
        self._root.setSpacing(14)

    # -- building blocks --------------------------------------------------- #
    def add_header(self, heading: str, body: str = "", logo_size: int = 76) -> None:
        row = QHBoxLayout()
        row.setSpacing(16)

        pic = QLabel()
        pic.setPixmap(logo_pixmap(logo_size))
        pic.setFixedSize(logo_size, logo_size)
        pic.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter)
        row.addWidget(pic, 0, Qt.AlignmentFlag.AlignTop)

        col = QVBoxLayout()
        col.setSpacing(6)

        head = QLabel(heading)
        head.setObjectName("DialogHeading")
        head.setWordWrap(True)
        col.addWidget(head)

        if body:
            text = QLabel(body)
            text.setObjectName("DialogBody")
            text.setWordWrap(True)
            col.addWidget(text)

        col.addStretch(1)
        row.addLayout(col, 1)
        self._root.addLayout(row)

    def add_widget(self, widget: QWidget) -> None:
        self._root.addWidget(widget)

    def add_buttons(self, specs) -> None:
        """specs: list of ``(text, value, is_primary)`` tuples."""
        row = QHBoxLayout()
        row.setSpacing(8)
        row.addStretch(1)
        for text, value, primary in specs:
            btn = QPushButton(text)
            if primary:
                btn.setObjectName("Primary")
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(lambda checked=False, v=value: self._pick(v))
            row.addWidget(btn)
        self._root.addLayout(row)

    def _pick(self, value: str) -> None:
        self.choice = value
        self.accept()


def show_dialog(parent, title: str, heading: str, body: str, specs) -> str | None:
    """Open a small logo dialog and return the value of the clicked button."""
    dlg = LogoDialog(parent, title)
    dlg.add_header(heading, body)
    dlg.add_buttons(specs)
    dlg.exec()
    return dlg.choice
class AdvancedDialog(LogoDialog):
    """Lets a power user pick exactly which AnyDesk steps to run."""

    def __init__(self, parent, options: dict, exe_path: str | None) -> None:
        super().__init__(parent, "Advanced options")
        self.options = dict(options)
        self.exe_path = exe_path
        self.boxes: dict[str, QCheckBox] = {}

        self.setMinimumWidth(540)
        self.add_header(
            "Advanced options",
            "Fine-tune exactly what the reset does. The defaults match AnyDesk.bat.",
            logo_size=64,
        )

        self._add_check("Stop the AnyDesk service  (machine-wide)", "stop_service")
        self._add_check("Close all AnyDesk / AnyDeskMSI processes", "kill_processes")
        self._add_check("Reset machine-wide config  (ProgramData)", "reset_machine")
        user_cb = self._add_check("Reset per-user config  (AppData)", "reset_user")
        wipe_cb = self._add_check("Wipe the AnyDesk ID / all settings  (new ID)", "wipe_id")
        wipe_cb.setObjectName("DangerCheck")
        self._add_check("Start AnyDesk when finished", "start_anydesk")

        user_cb.toggled.connect(self._sync_wipe)
        self._sync_wipe(user_cb.isChecked())

        # ---- AnyDesk location -------------------------------------------- #
        loc_row = QHBoxLayout()
        loc_row.setSpacing(8)

        self.path_label = QLabel()
        self.path_label.setObjectName("PathLabel")
        self.path_label.setWordWrap(True)
        loc_row.addWidget(self.path_label, 1)

        detect_btn = QPushButton("Re-detect")
        detect_btn.clicked.connect(self._redetect)
        open_btn = QPushButton("Open folder")
        open_btn.clicked.connect(self._open_folder)
        for btn in (detect_btn, open_btn):
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            loc_row.addWidget(btn)

        self._root.addLayout(loc_row)
        self._update_path_label()

        defaults_btn = QPushButton("Restore recommended defaults")
        defaults_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        defaults_btn.clicked.connect(self._restore_defaults)
        self.add_widget(defaults_btn)

        self.add_buttons([("Cancel", "cancel", False), ("Save", "save", True)])

    # -- helpers ----------------------------------------------------------- #
    def _add_check(self, text: str, key: str) -> QCheckBox:
        cb = QCheckBox(text)
        cb.setChecked(bool(self.options.get(key, False)))
        self.boxes[key] = cb
        self.add_widget(cb)
        return cb

    def _sync_wipe(self, enabled: bool) -> None:
        cb = self.boxes["wipe_id"]
        cb.setEnabled(enabled)
        if not enabled:
            cb.setChecked(False)

    def _update_path_label(self) -> None:
        if self.exe_path:
            self.path_label.setText(f"AnyDesk.exe :  {self.exe_path}")
        else:
            self.path_label.setText("AnyDesk.exe :  not found")

    def _redetect(self) -> None:
        self.exe_path = find_anydesk_exe()
        self._update_path_label()

    def _open_folder(self) -> None:
        candidates = []
        program_data = os.environ.get("ProgramData")
        app_data = os.environ.get("APPDATA")
        if program_data:
            candidates.append(Path(program_data) / "AnyDesk")
        if app_data:
            candidates.append(Path(app_data) / "AnyDesk")

        for folder in candidates:
            try:
                if folder.is_dir():
                    os.startfile(str(folder))  # noqa: S606 - Windows shell open
                    return
            except OSError:
                continue

        show_dialog(
            self,
            APP_NAME,
            "No data folder yet",
            "AnyDesk has not created its configuration folder on this PC yet.",
            [("OK", "ok", True)],
        )

    def _restore_defaults(self) -> None:
        for key, cb in self.boxes.items():
            cb.setChecked(bool(DEFAULT_OPTIONS.get(key, False)))
        self._sync_wipe(self.boxes["reset_user"].isChecked())

    def _pick(self, value: str) -> None:
        if value == "save":
            for key, cb in self.boxes.items():
                self.options[key] = cb.isChecked()
        super()._pick(value)
class DetailsDialog(LogoDialog):
    """Scrollable log window - also carries the logo."""

    def __init__(self, parent, log_text: str) -> None:
        super().__init__(parent, "Cleanup details")
        self.setMinimumSize(640, 460)

        self.add_header(
            "Cleanup details", "Everything that happened, step by step.", logo_size=56
        )

        view = QPlainTextEdit()
        view.setObjectName("LogView")
        view.setReadOnly(True)
        view.setPlainText(log_text)
        font = QFont("Consolas")
        font.setStyleHint(QFont.StyleHint.Monospace)
        font.setPointSize(9)
        view.setFont(font)
        self._root.addWidget(view, 1)

        copy_btn = QPushButton("Copy to clipboard")
        copy_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        copy_btn.clicked.connect(lambda: QApplication.clipboard().setText(log_text))
        self.add_widget(copy_btn)

        self.add_buttons([("Close", "close", True)])
# --------------------------------------------------------------------------- #
#  Background worker
# --------------------------------------------------------------------------- #
class ResetWorker(QThread):
    """Runs the AnyDesk cleanup sequence off the GUI thread."""

    log = pyqtSignal(str)
    stage = pyqtSignal(str)
    progress = pyqtSignal(int)
    done = pyqtSignal(bool)

    def __init__(self, options: dict, parent=None) -> None:
        super().__init__(parent)
        self.options = options

    # -- small helpers ------------------------------------------------------ #
    def _say(self, text: str = "") -> None:
        self.log.emit(text)

    def _cmd(self, args) -> tuple[int, str]:
        args = [str(a) for a in args]
        self._say("> " + " ".join(args))
        code, output = run_cmd(args)
        if output:
            for line in output.splitlines():
                self._say("      " + line)
        return code, output

    # -- individual jobs ---------------------------------------------------- #
    def _job_service(self) -> None:
        code, _ = self._cmd(["sc", "query", SERVICE_NAME])
        if code == 0:
            self._cmd(["net", "stop", SERVICE_NAME])
            self._cmd(["sc", "stop", SERVICE_NAME])
            self._say("      Service stop requested.")
        else:
            self._say("      No AnyDesk service found - skipping.")

    def _job_processes(self) -> None:
        for name in PROCESS_NAMES:
            code, _ = self._cmd(["taskkill", "/F", "/IM", name])
            if code != 0:
                self._say(f"      {name} was not running.")
        self._say("      Waiting 2 seconds for handles to be released...")
        time.sleep(2)

    def _job_config(self) -> None:
        targets: list[Path] = []

        if self.options["reset_machine"]:
            program_data = os.environ.get("ProgramData")
            if program_data:
                ad = Path(program_data) / "AnyDesk"
                targets.append(ad / "service.conf")
                targets.append(ad / "system.conf")

        if self.options["reset_user"]:
            app_data = os.environ.get("APPDATA")
            if app_data:
                ad = Path(app_data) / "AnyDesk"
                targets.append(ad / "system.conf")
                if self.options["wipe_id"]:
                    targets.append(ad / "user.conf")

        if not targets:
            self._say("      Nothing selected - skipping.")
            return

        for path in targets:
            try:
                if path.is_file():
                    path.unlink()
                    self._say(f"      deleted : {path}")
                else:
                    self._say(f"      missing : {path}   (nothing to delete)")
            except OSError as exc:
                self._say(f"      FAILED  : {path}   ({exc})")

    def _job_start(self) -> None:
        exe = self.options.get("exe_path") or find_anydesk_exe()
        if not exe:
            self._say("      WARNING: AnyDesk.exe was not found on this PC.")
            self._say("      Install AnyDesk first, then run this tool again.")
            return
        self._say(f"      Found: {exe}")
        try:
            os.startfile(exe)  # noqa: S606 - Windows shell launch ("start")
            self._say("      AnyDesk launched.")
        except Exception as exc:
            self._say(f"      Failed to launch AnyDesk: {exc}")

    # -- orchestration ------------------------------------------------------ #
    def _build_jobs(self) -> list[tuple[str, object]]:
        jobs: list[tuple[str, object]] = []
        if self.options["stop_service"]:
            jobs.append(("Stop AnyDesk service", self._job_service))
        if self.options["kill_processes"]:
            jobs.append(("Close AnyDesk processes", self._job_processes))
        if self.options["reset_machine"] or self.options["reset_user"]:
            jobs.append(("Reset AnyDesk configuration files", self._job_config))
        if self.options["start_anydesk"]:
            jobs.append(("Locate and start AnyDesk", self._job_start))
        return jobs

    def run(self) -> None:
        jobs = self._build_jobs()
        total = max(len(jobs), 1)

        self._say(f"=== {APP_NAME} ===")
        self._say(f"Administrator rights : {'YES' if is_admin() else 'NO'}")
        self._say("")

        if not jobs:
            self._say("No operations selected.")
            self.stage.emit("Nothing to do.")
            self.progress.emit(100)
            self.done.emit(False)
            return

        success = True
        for index, (title, func) in enumerate(jobs, start=1):
            header = f"[{index}/{len(jobs)}] {title}"
            self.stage.emit(header)
            self._say(f"{header}...")
            try:
                func()
            except Exception as exc:  # keep going, report the failure
                success = False
                self._say(f"      ERROR: {exc}")
            self.progress.emit(int(index / total * 100))
            self._say("")

        self._say("Finished successfully." if success else "Finished with errors.")
        self.done.emit(success)
# --------------------------------------------------------------------------- #
#  Main window - deliberately simple: logo, one button, one checkbox
# --------------------------------------------------------------------------- #
class MainWindow(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.worker: ResetWorker | None = None
        self.options: dict = dict(DEFAULT_OPTIONS)
        self.exe_path: str | None = find_anydesk_exe()
        self.log_lines: list[str] = []

        self.setWindowTitle(APP_NAME)
        icon = QIcon(logo_pixmap(256))
        if not icon.isNull():
            self.setWindowIcon(icon)

        self.setFixedWidth(500)
        self._build_ui()
        self._refresh_status()

    # -- user interface ----------------------------------------------------- #
    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(30, 26, 30, 24)
        root.setSpacing(14)

        logo = QLabel()
        logo.setPixmap(logo_pixmap(150))
        logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        root.addWidget(logo)

        title = QLabel(APP_NAME)
        title.setObjectName("Title")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        root.addWidget(title)

        tagline = QLabel("Resets AnyDesk to clear its session timer.")
        tagline.setObjectName("Tagline")
        tagline.setAlignment(Qt.AlignmentFlag.AlignCenter)
        root.addWidget(tagline)

        root.addWidget(self._build_status_pill(), 0, Qt.AlignmentFlag.AlignHCenter)

        # ---- the one big action ------------------------------------------ #
        self.run_btn = QPushButton("Reset AnyDesk")
        self.run_btn.setObjectName("Hero")
        self.run_btn.setMinimumHeight(58)
        self.run_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.run_btn.clicked.connect(self._run)
        root.addWidget(self.run_btn)

        self.cb_new_id = QCheckBox("Give me a brand-new AnyDesk ID")
        self.cb_new_id.setToolTip(
            "Also deletes user.conf, so AnyDesk generates a fresh ID next launch."
        )
        self.cb_new_id.setChecked(self.options["wipe_id"])
        self.cb_new_id.toggled.connect(self._on_new_id_toggled)
        root.addWidget(self.cb_new_id, 0, Qt.AlignmentFlag.AlignHCenter)

        advanced_btn = QPushButton("Advanced options...")
        advanced_btn.setObjectName("Link")
        advanced_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        advanced_btn.clicked.connect(self._open_advanced)
        root.addWidget(advanced_btn, 0, Qt.AlignmentFlag.AlignHCenter)

        # ---- progress / status ------------------------------------------- #
        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.progress.setVisible(False)
        root.addWidget(self.progress)

        self.status = QLabel("")
        self.status.setObjectName("Status")
        self.status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status.setWordWrap(True)
        root.addWidget(self.status)

    def _build_status_pill(self) -> QFrame:
        self.pill = QFrame()
        self.pill.setObjectName("Pill")

        row = QHBoxLayout(self.pill)
        row.setContentsMargins(14, 7, 14, 7)
        row.setSpacing(10)

        self.pill_label = QLabel()
        self.pill_label.setObjectName("PillText")

        self.retry_btn = QPushButton("Retry")
        self.retry_btn.setObjectName("Small")
        self.retry_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.retry_btn.clicked.connect(self._retry_elevate)

        row.addWidget(self.pill_label)
        row.addWidget(self.retry_btn)
        return self.pill
    # -- state -------------------------------------------------------------- #
    @staticmethod
    def _restyle(widget: QWidget) -> None:
        """Force Qt to re-evaluate dynamic-property stylesheets."""
        widget.style().unpolish(widget)
        widget.style().polish(widget)

    def _refresh_status(self) -> None:
        if is_admin():
            self.pill.setProperty("state", "ok")
            self.pill_label.setText("\u2714  Running as Administrator")
            self.retry_btn.setVisible(False)
        else:
            self.pill.setProperty("state", "warn")
            self.pill_label.setText("\u26a0  Not running as Administrator")
            self.retry_btn.setVisible(True)
        self._restyle(self.pill)
        self.pill_label.adjustSize()
        self.pill.adjustSize()

    def _retry_elevate(self) -> None:
        if is_admin():
            self._refresh_status()
            return
        if launch_elevated_consoleless():
            QApplication.quit()
        else:
            self.status.setText("Elevation was cancelled. Some steps may fail.")

    def _on_new_id_toggled(self, checked: bool) -> None:
        self.options["wipe_id"] = checked
        if checked and not self.options["reset_user"]:
            # user.conf only gets deleted as part of the per-user reset
            self.options["reset_user"] = True

    def _open_advanced(self) -> None:
        dlg = AdvancedDialog(self, self.options, self.exe_path)
        dlg.exec()
        if dlg.choice == "save":
            self.options = dlg.options
            self.exe_path = dlg.exe_path
            self.cb_new_id.blockSignals(True)
            self.cb_new_id.setChecked(self.options["wipe_id"])
            self.cb_new_id.blockSignals(False)

    def _set_running(self, running: bool) -> None:
        self.run_btn.setEnabled(not running)
        self.cb_new_id.setEnabled(not running)
        self.run_btn.setText("Working..." if running else "Reset AnyDesk")

    # -- running ------------------------------------------------------------ #
    def _on_log(self, text: str) -> None:
        self.log_lines.append(text)

    def _run(self) -> None:
        if self.worker is not None and self.worker.isRunning():
            return

        opts = dict(self.options)
        opts["exe_path"] = self.exe_path

        if not any(
            opts[k]
            for k in (
                "stop_service",
                "kill_processes",
                "reset_machine",
                "reset_user",
                "start_anydesk",
            )
        ):
            show_dialog(
                self,
                APP_NAME,
                "Nothing selected",
                "Open Advanced options and pick at least one step, then try again.",
                [("OK", "ok", True)],
            )
            return

        self.log_lines = []
        self.progress.setValue(0)
        self.progress.setVisible(True)
        self.status.setText("Working, please wait...")
        self._set_running(True)

        self.worker = ResetWorker(opts, self)
        self.worker.log.connect(self._on_log)
        self.worker.stage.connect(self.status.setText)
        self.worker.progress.connect(self.progress.setValue)
        self.worker.done.connect(self._on_done)
        self.worker.finished.connect(self._on_thread_finished)
        self.worker.start()

    def _on_done(self, success: bool) -> None:
        self.progress.setValue(100)
        self._set_running(False)
        self._refresh_status()

        text = "\n".join(self.log_lines)

        if success:
            self.status.setText("Done.")
            body = "AnyDesk has been reset"
            body += " and restarted." if self.options["start_anydesk"] else "."
            choice = show_dialog(
                self,
                APP_NAME,
                "All done!",
                body,
                [("Show details", "details", False), ("Close", "close", True)],
            )
        else:
            self.status.setText("Finished with errors.")
            choice = show_dialog(
                self,
                APP_NAME,
                "Finished with errors",
                "Some steps could not complete. Running as Administrator usually fixes it.",
                [("Show details", "details", True), ("Close", "close", False)],
            )

        if choice == "details":
            DetailsDialog(self, text).exec()

    def _on_thread_finished(self) -> None:
        if self.worker is not None:
            self.worker.deleteLater()
            self.worker = None

    def closeEvent(self, event) -> None:
        if self.worker is not None and self.worker.isRunning():
            choice = show_dialog(
                self,
                APP_NAME,
                "Still working",
                "An operation is still running. Quit anyway?",
                [("Keep running", "wait", True), ("Quit anyway", "quit", False)],
            )
            if choice != "quit":
                event.ignore()
                return
            self.worker.terminate()
            self.worker.wait(2000)
        event.accept()
# --------------------------------------------------------------------------- #
#  Styling
# --------------------------------------------------------------------------- #
STYLESHEET = """
QWidget {
    background: #1c1d20;
    color: #e8e8e8;
    font-family: 'Segoe UI', 'Noto Sans', sans-serif;
    font-size: 13px;
}

QLabel#Title { font-size: 24px; font-weight: 700; color: #ffffff; }
QLabel#Tagline { color: #9aa0a8; }
QLabel#Status { color: #9aa0a8; font-size: 12px; }
QLabel#DialogHeading { font-size: 17px; font-weight: 700; color: #ffffff; }
QLabel#DialogBody { color: #b9bec6; }
QLabel#PathLabel { color: #8fd694; font-family: 'Consolas', monospace; font-size: 12px; }

QFrame#Pill { border-radius: 15px; }
QFrame#Pill[state="ok"] { background: #16301d; border: 1px solid #2e7d32; }
QFrame#Pill[state="warn"] { background: #33291a; border: 1px solid #b8860b; }
QFrame#Pill[state="ok"] QLabel#PillText { color: #8fd694; }
QFrame#Pill[state="warn"] QLabel#PillText { color: #f0c46a; }

QPushButton {
    background: #33363b;
    border: 1px solid #45484e;
    border-radius: 7px;
    padding: 8px 16px;
}
QPushButton:hover { background: #3e4147; }
QPushButton:pressed { background: #2b2e32; }
QPushButton:disabled { color: #7a7a7a; background: #26282c; border-color: #303338; }

QPushButton#Hero {
    background: #d92b2b;
    border: 1px solid #f05252;
    border-radius: 10px;
    font-size: 19px;
    font-weight: 700;
    color: #ffffff;
    padding: 10px 24px;
}
QPushButton#Hero:hover { background: #ec3a3a; }
QPushButton#Hero:pressed { background: #b82020; }
QPushButton#Hero:disabled { background: #55302f; color: #9d9d9d; border-color: #6a3a39; }

QPushButton#Primary {
    background: #d92b2b;
    border: 1px solid #f05252;
    font-weight: 700;
    color: #ffffff;
}
QPushButton#Primary:hover { background: #ec3a3a; }

QPushButton#Link {
    background: transparent;
    border: none;
    color: #8fb8ff;
    padding: 4px 8px;
}
QPushButton#Link:hover { color: #b6d0ff; }

QPushButton#Small {
    background: #3f4249;
    border: 1px solid #54585f;
    border-radius: 6px;
    padding: 3px 12px;
    font-size: 12px;
}

QCheckBox { spacing: 9px; }
QCheckBox::indicator {
    width: 18px; height: 18px;
    border: 1px solid #6a6e75;
    border-radius: 5px;
    background: #2a2d31;
}
QCheckBox::indicator:hover { border-color: #f05252; }
QCheckBox::indicator:checked { background: #d92b2b; border: 1px solid #f05252; }
QCheckBox#DangerCheck { color: #ff8a8a; }
QCheckBox:disabled { color: #7a7a7a; }

QProgressBar {
    border: 1px solid #3a3d43;
    border-radius: 7px;
    background: #2a2d31;
    height: 16px;
    text-align: center;
    color: #e8e8e8;
    font-size: 11px;
}
QProgressBar::chunk { background: #d92b2b; border-radius: 6px; }

QPlainTextEdit#LogView {
    background: #141518;
    border: 1px solid #3a3d43;
    border-radius: 8px;
    padding: 8px;
    color: #cfd3d8;
    selection-background-color: #d92b2b;
}

QDialog { background: #1c1d20; }
"""


# --------------------------------------------------------------------------- #
#  Entry point
# --------------------------------------------------------------------------- #
def main() -> int:
    argv = list(sys.argv)

    already_relaunched = RELAUNCH_FLAG in argv
    skip_elevation = NO_ELEVATE_FLAG in argv or os.environ.get("ATR_NO_ELEVATE") == "1"

    # ---- Default behaviour: become Administrator, with NO console window ---
    # We re-launch through pythonw.exe + UAC, then hand over to that instance.
    if not already_relaunched and not skip_elevation:
        if not is_admin() or console_attached():
            if launch_elevated_consoleless():
                return 0

    # Qt must never see our private flags.
    qt_argv = [a for a in argv if a not in (RELAUNCH_FLAG, NO_ELEVATE_FLAG)]
    sys.argv = qt_argv

    app = QApplication(qt_argv)
    app.setApplicationName(APP_NAME)
    app.setApplicationDisplayName(APP_NAME)
    app.setStyleSheet(STYLESHEET)

    icon = QIcon(logo_pixmap(256))
    if not icon.isNull():
        app.setWindowIcon(icon)

    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
