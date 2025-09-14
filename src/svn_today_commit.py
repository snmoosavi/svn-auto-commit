# -*- coding: utf-8 -*-
"""
SVN Auto Commit — PyQt5 (Today-Only Commits)
Select ANY folder/drive. The app discovers ALL SVN working copies inside it.
It watches changes and ONLY commits items changed "today" (local date).
- Update Now: full update across all working copies.
- Auto-commit after debounce only for today's changed items (A/M/D).
- Minimizes to System Tray; Exit button to quit.
- Material-ish soft theme, English UI.

Run:
  pip install PyQt5
  python src/svn_today_commit.py
"""

import os
import sys
import time
import getpass
import subprocess
from datetime import datetime, date, timedelta
from typing import Dict, Tuple, Set, List, Optional

from PyQt5.QtCore import (
    Qt, QTimer, QSize, QSettings, QEvent, QRect
)
from PyQt5.QtGui import (
    QIcon, QPainter, QPixmap, QColor, QCloseEvent
)
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QLabel, QLineEdit, QPushButton,
    QToolButton, QCheckBox, QFileDialog, QHBoxLayout, QVBoxLayout,
    QPlainTextEdit, QSpinBox, QGroupBox, QFormLayout, QMessageBox,
    QSystemTrayIcon, QMenu, QAction, QStyle
)

APP_ORG = "AriaVision"
APP_NAME = "SVN Auto Commit (Today Only)"
VERSION = "2.0.0"

# --------------------------- Helpers ---------------------------

def find_default_tortoiseproc() -> str:
    for p in [
        r"C:\\Program Files\\TortoiseSVN\\bin\\TortoiseProc.exe",
        r"C:\\Program Files (x86)\\TortoiseSVN\\bin\\TortoiseProc.exe",
    ]:
        if os.path.isfile(p):
            return p
    return ""

def find_default_svn() -> str:
    for p in os.getenv("PATH", "").split(os.pathsep):
        exe = os.path.join(p, "svn.exe")
        if os.path.isfile(exe):
            return "svn.exe"
    for p in [
        r"C:\\Program Files\\TortoiseSVN\\bin\\svn.exe",
        r"C:\\Program Files (x86)\\TortoiseSVN\\bin\\svn.exe",
        r"C:\\Program Files\\Subversion\\bin\\svn.exe",
        r"C:\\Program Files\\SlikSvn\\bin\\svn.exe",
    ]:
        if os.path.isfile(p):
            return p
    return ""

def make_app_icon(size: int = 256, fg="#2e7d32", bg="#e8f5e9") -> QIcon:
    pm = QPixmap(size, size); pm.fill(Qt.transparent)
    p = QPainter(pm); p.setRenderHint(QPainter.Antialiasing, True)
    p.setBrush(QColor(bg)); p.setPen(Qt.NoPen); p.drawEllipse(0, 0, size, size)
    pen = p.pen(); pen.setColor(QColor(fg)); pen.setWidth(int(size * 0.06))
    pen.setCapStyle(Qt.RoundCap); pen.setJoinStyle(Qt.RoundJoin); p.setPen(pen)
    w = size
    p.drawLine(int(w*0.25), int(w*0.55), int(w*0.42), int(w*0.72))
    p.drawLine(int(w*0.42), int(w*0.72), int(w*0.78), int(w*0.34))
    p.end()
    return QIcon(pm)

def soft_material_stylesheet() -> str:
    return """
    QWidget { font-family: Segoe UI, Roboto, Arial; font-size: 11pt; color: #263238; }
    QMainWindow, QDialog, QWidget { background: #fafafa; }
    QGroupBox { border: 1px solid #e0e0e0; border-radius: 10px; margin-top: 10px; background: #ffffff; }
    QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 6px; color: #00695c; }
    QLineEdit, QPlainTextEdit, QSpinBox {
        background: #ffffff; border: 1px solid #e0e0e0; border-radius: 8px; padding: 6px 8px;
    }
    QPushButton, QToolButton {
        background: #e8f5e9; border: 1px solid #c8e6c9; border-radius: 10px; padding: 8px 14px;
    }
    QPushButton:hover, QToolButton:hover { background: #dcf5e0; }
    QPushButton:pressed, QToolButton:pressed { background: #cdeed2; }
    QLabel.subtle { color: #607d8b; }
    QToolTip { background: #263238; color: #ECEFF1; border: 0px; }
    """

def run_cmd(args: List[str], cwd: Optional[str] = None, hide=True, timeout: int = 600):
    startupinfo = None; creationflags = 0
    if hide and os.name == "nt":
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        creationflags = subprocess.CREATE_NO_WINDOW
    try:
        proc = subprocess.run(
            args, cwd=cwd, capture_output=True, text=True, timeout=timeout,
            startupinfo=startupinfo, creationflags=creationflags, shell=False
        )
        return proc.returncode, proc.stdout.strip(), proc.stderr.strip()
    except FileNotFoundError as e:
        return 127, "", str(e)
    except Exception as e:
        return 128, "", str(e)

def human_time() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def start_of_today() -> datetime:
    now = datetime.now()
    return datetime(now.year, now.month, now.day, 0, 0, 0)

def is_ignored(path: str) -> bool:
    name = os.path.basename(path).lower()
    if name in {".svn"}: return True
    if name.endswith((".tmp", ".swp", ".swo", ".pyc", ".pyo", "~")): return True
    return False

def snapshot_tree(root: str) -> Dict[str, Tuple[float, int]]:
    """
    Return {filepath: (mtime, size)} recursively, skipping .svn and ignored.
    For very large trees (e.g., drive root), consider increasing scan interval.
    """
    state: Dict[str, Tuple[float, int]] = {}
    for base, dirs, files in os.walk(root):
        dirs[:] = [d for d in dirs if d.lower() != ".svn"]
        for fn in files:
            fp = os.path.join(base, fn)
            if is_ignored(fp): continue
            try:
                st = os.stat(fp)
                state[fp] = (st.st_mtime, st.st_size)
            except (FileNotFoundError, PermissionError):
                continue
    return state

def diff_states(old: Dict[str, Tuple[float, int]], new: Dict[str, Tuple[float, int]]):
    old_keys, new_keys = set(old.keys()), set(new.keys())
    added = new_keys - old_keys
    removed = old_keys - new_keys
    modified = {k for k in (new_keys & old_keys) if old[k] != new[k]}
    return added, removed, modified

def find_working_copy_roots(root: str) -> List[str]:
    """
    Find all directories under 'root' that contain a '.svn' folder.
    Externals are also found (they have their own .svn).
    """
    wc_roots: List[str] = []
    for base, dirs, files in os.walk(root):
        if ".svn" in (d.lower() for d in dirs):
            wc_roots.append(base)
    wc_roots = sorted(set(wc_roots), key=lambda p: (len(p), p.lower()))
    return wc_roots

def is_under(path: str, parent: str) -> bool:
    try:
        common = os.path.commonpath([os.path.abspath(path), os.path.abspath(parent)])
        return common == os.path.abspath(parent)
    except Exception:
        return False

# --------------------------- Main Window ---------------------------

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(APP_NAME)
        self.setWindowIcon(make_app_icon())
        self.resize(600, 440)

        # State
        self.monitoring = False
        self.root_folder = ""
        self.timer = QTimer(self); self.timer.setInterval(2000)
        self.timer.timeout.connect(self.on_tick)
        self.debounce_ms = 5000
        self.last_change_ts = 0.0
        self.pending_commit = False

        # File state snapshots
        self.prev_state: Dict[str, Tuple[float, int]] = {}
        self.wc_roots: List[str] = []

        # Today tracking
        self.today_zero = start_of_today()
        # Map: wc_root -> { path -> change_type('A','M','D') }
        self.changed_today: Dict[str, Dict[str, str]] = {}

        # Settings
        self.settings = QSettings(APP_ORG, APP_NAME)
        self.load_settings()

        # UI + Tray
        self.build_ui()
        self.apply_bottom_right_position()
        self.build_tray()
        self.setStyleSheet(soft_material_stylesheet())

        # Bootstrapping
        if self.root_folder and os.path.isdir(self.root_folder):
            self.prev_state = snapshot_tree(self.root_folder)
            self.refresh_wc_roots()

    # --------------------------- UI ---------------------------

    def build_ui(self):
        w = QWidget(); self.setCentralWidget(w)

        self.folder_edit = QLineEdit(self.root_folder)
        self.folder_edit.setPlaceholderText("Choose ANY folder/drive to watch recursively…")
        btn_browse = QToolButton(); btn_browse.setText("Browse")
        btn_browse.setToolTip("Select root folder (recursively scans all subfolders)")
        btn_browse.clicked.connect(self.choose_folder)

        self.btn_start = QPushButton("Start")
        self.btn_stop = QPushButton("Stop")
        self.btn_update = QPushButton("Update Now")
        self.btn_exit = QPushButton("Exit")

        self.btn_start.clicked.connect(self.start_monitor)
        self.btn_stop.clicked.connect(self.stop_monitor)
        self.btn_update.clicked.connect(self.do_update)
        self.btn_exit.clicked.connect(self.exit_app)

        grp = QGroupBox("Settings"); form = QFormLayout()

        self.use_svn_cli = QCheckBox("Prefer svn.exe for silent commits")
        self.auto_update_before_commit = QCheckBox("Auto update before each commit")

        self.debounce_spin = QSpinBox(); self.debounce_spin.setRange(500, 60000)
        self.debounce_spin.setSingleStep(500); self.debounce_spin.setValue(self.debounce_ms); self.debounce_spin.setSuffix(" ms")
        self.scan_spin = QSpinBox(); self.scan_spin.setRange(500, 20000)
        self.scan_spin.setSingleStep(500); self.scan_spin.setValue(self.timer.interval()); self.scan_spin.setSuffix(" ms")
        self.scan_spin.valueChanged.connect(self.timer.setInterval)

        self.commit_prefix = QLineEdit("Auto-commit (Today)")
        self.svn_path_edit = QLineEdit(find_default_svn())
        self.tp_path_edit = QLineEdit(find_default_tortoiseproc())

        # Load persisted
        self.use_svn_cli.setChecked(self.settings.value("use_svn_cli", True, type=bool))
        self.auto_update_before_commit.setChecked(self.settings.value("auto_update_before_commit", True, type=bool))
        self.commit_prefix.setText(self.settings.value("commit_prefix", "Auto-commit (Today)", type=str))
        if self.settings.value("svn_path", "", type=str): self.svn_path_edit.setText(self.settings.value("svn_path", "", type=str))
        if self.settings.value("tortoiseproc_path", "", type=str): self.tp_path_edit.setText(self.settings.value("tortoiseproc_path", "", type=str))

        form.addRow(QLabel(""), QLabel("Only today's changed items are included in commits."))
        form.addRow("Debounce:", self.debounce_spin)
        form.addRow("Scan Interval:", self.scan_spin)
        form.addRow("Commit Prefix:", self.commit_prefix)
        form.addRow("Prefer svn.exe:", self.use_svn_cli)
        form.addRow("Auto Update before Commit:", self.auto_update_before_commit)
        form.addRow("svn.exe:", self.svn_path_edit)
        form.addRow("TortoiseProc.exe:", self.tp_path_edit)
        grp.setLayout(form)

        self.log = QPlainTextEdit(); self.log.setReadOnly(True)
        self.log.setPlaceholderText("Logs will appear here…")

        row1 = QHBoxLayout(); row1.addWidget(QLabel("Folder:")); row1.addWidget(self.folder_edit); row1.addWidget(btn_browse)
        row2 = QHBoxLayout()
        for b in (self.btn_start, self.btn_stop, self.btn_update, self.btn_exit):
            b.setIcon(self.icon_for_button(b.text())); row2.addWidget(b)
        row2.addStretch(1)

        v = QVBoxLayout()
        v.addLayout(row1); v.addLayout(row2); v.addWidget(grp); v.addWidget(QLabel("Activity Log:")); v.addWidget(self.log)
        tip = QLabel("Tip: Close the window to send it to the system tray."); tip.setObjectName("tipLbl"); v.addWidget(tip)
        w.setLayout(v)

    def icon_for_button(self, label: str) -> QIcon:
        s = self.style()
        if "Start" in label: return s.standardIcon(QStyle.SP_MediaPlay)
        if "Stop" in label: return s.standardIcon(QStyle.SP_MediaStop)
        if "Update" in label: return s.standardIcon(QStyle.SP_BrowserReload)
        if "Exit" in label: return s.standardIcon(QStyle.SP_DialogCloseButton)
        return QIcon()

    def build_tray(self):
        self.tray = QSystemTrayIcon(self); self.tray.setIcon(self.windowIcon())
        menu = QMenu()
        act_open = QAction("Open", self); act_open.triggered.connect(self.show_normal_from_tray)
        act_update = QAction("Update Now", self); act_update.triggered.connect(self.do_update)
        self.act_toggle = QAction("Start Monitoring", self); self.act_toggle.triggered.connect(self.toggle_monitoring)
        act_exit = QAction("Exit", self); act_exit.triggered.connect(self.exit_app)
        menu.addAction(act_open); menu.addAction(act_update); menu.addSeparator(); menu.addAction(self.act_toggle)
        menu.addSeparator(); menu.addAction(act_exit)
        self.tray.setContextMenu(menu); self.tray.activated.connect(self.on_tray_activated); self.tray.show()

    def on_tray_activated(self, reason):
        if reason == QSystemTrayIcon.Trigger: self.show_normal_from_tray()

    def show_normal_from_tray(self):
        self.show(); self.activateWindow(); self.raise_(); self.apply_bottom_right_position()

    def apply_bottom_right_position(self):
        screen = QApplication.primaryScreen()
        if not screen: return
        g: QRect = screen.availableGeometry(); margin = 10
        x = g.right() - self.width() - margin; y = g.bottom() - self.height() - margin
        self.move(max(g.left(), x), max(g.top(), y))

    # --------------------------- Settings ---------------------------

    def load_settings(self):
        self.root_folder = self.settings.value("root_folder", "", type=str)

    def save_settings(self):
        self.settings.setValue("root_folder", self.root_folder)
        self.settings.setValue("svn_path", self.svn_path_edit.text().strip())
        self.settings.setValue("tortoiseproc_path", self.tp_path_edit.text().strip())
        self.settings.setValue("use_svn_cli", self.use_svn_cli.isChecked())
        self.settings.setValue("auto_update_before_commit", self.auto_update_before_commit.isChecked())
        self.settings.setValue("commit_prefix", self.commit_prefix.text().strip())

    # --------------------------- Events ---------------------------

    def closeEvent(self, event: QCloseEvent):
        event.ignore(); self.hide()
        self.tray.showMessage(APP_NAME, "Still running in the system tray.", QSystemTrayIcon.Information, 2500)

    def changeEvent(self, e: QEvent):
        if e.type() == QEvent.WindowStateChange and self.windowState() & Qt.WindowMinimized:
            QTimer.singleShot(0, self.hide)

    # --------------------------- Actions ---------------------------

    def choose_folder(self):
        d = QFileDialog.getExistingDirectory(self, "Choose Root Folder", self.root_folder or os.path.expanduser("~"))
        if d:
            self.root_folder = d; self.folder_edit.setText(d)
            self.prev_state = snapshot_tree(d)
            self.refresh_wc_roots()
            self.reset_today()
            self.log_info(f"Watching: {d}")
            self.save_settings()

    def start_monitor(self):
        if not self.validate_paths(): return
        if not self.root_folder or not os.path.isdir(self.root_folder):
            self.warn("Please choose a valid folder first."); return
        self.debounce_ms = self.debounce_spin.value()
        self.timer.start(); self.monitoring = True; self.act_toggle.setText("Stop Monitoring")
        self.log_info("Monitoring started.")

    def stop_monitor(self):
        self.timer.stop(); self.monitoring = False; self.act_toggle.setText("Start Monitoring")
        self.log_info("Monitoring stopped.")

    def toggle_monitoring(self):
        self.stop_monitor() if self.monitoring else self.start_monitor()

    def exit_app(self):
        self.stop_monitor(); self.tray.hide(); QApplication.instance().quit()

    # --------------------------- Monitor loop ---------------------------

    def on_tick(self):
        # Handle date rollover at midnight:
        if datetime.now() >= self.today_zero + timedelta(days=1):
            self.reset_today()

        if not self.root_folder: return
        new_state = snapshot_tree(self.root_folder)
        added, removed, modified = diff_states(self.prev_state, new_state)
        if added or removed or modified:
            self.prev_state = new_state
            self.record_today_changes(added, removed, modified)
            total = len(added) + len(removed) + len(modified)
            self.log_info(f"Detected changes: +{len(added)} / -{len(removed)} / ~{len(modified)} (total {total})")
            self.last_change_ts = time.time(); self.pending_commit = True

        if self.pending_commit and (time.time() - self.last_change_ts) * 1000 >= self.debounce_ms:
            self.pending_commit = False
            self.perform_commit_today_only()

    def reset_today(self):
        self.today_zero = start_of_today()
        self.changed_today = {wc: {} for wc in self.wc_roots}
        self.log_info("New day detected. Today's change list cleared.")

    def refresh_wc_roots(self):
        self.wc_roots = find_working_copy_roots(self.root_folder)
        self.changed_today = {wc: {} for wc in self.wc_roots}
        if self.wc_roots:
            self.log_info(f"Found {len(self.wc_roots)} working copy root(s).")
            for p in self.wc_roots[:10]: self.append_log(f"  • {p}")
            if len(self.wc_roots) > 10: self.append_log(f"  • … and {len(self.wc_roots)-10} more")
        else:
            self.log_warn("No SVN working copy found under selected folder.")

    def nearest_wc_root(self, path: str) -> Optional[str]:
        best = None; best_len = -1
        for wc in self.wc_roots:
            if is_under(path, wc):
                L = len(wc)
                if L > best_len:
                    best, best_len = wc, L
        return best

    def record_today_changes(self, added: Set[str], removed: Set[str], modified: Set[str]):
        # Only record changes whose timestamp is today (for existing files we can check mtime).
        # For deletions, we record the detection time (which is now); so if it's today, include.
        now = datetime.now()
        for fp in added:
            if is_ignored(fp): continue
            wc = self.nearest_wc_root(fp)
            if not wc: continue
            try:
                mtime = datetime.fromtimestamp(os.path.getmtime(fp))
                if mtime >= self.today_zero:
                    self.changed_today.setdefault(wc, {})[fp] = 'A'
            except Exception:
                continue

        for fp in modified:
            if is_ignored(fp): continue
            wc = self.nearest_wc_root(fp)
            if not wc: continue
            try:
                mtime = datetime.fromtimestamp(os.path.getmtime(fp))
                if mtime >= self.today_zero:
                    self.changed_today.setdefault(wc, {})[fp] = 'M'
            except Exception:
                continue

        for fp in removed:
            if is_ignored(fp): continue
            wc = self.nearest_wc_root(fp)
            if not wc: continue
            if now >= self.today_zero:
                self.changed_today.setdefault(wc, {})[fp] = 'D'

    # --------------------------- SVN Ops ---------------------------

    def validate_paths(self) -> bool:
        self.save_settings()
        ok = True
        if self.use_svn_cli.isChecked() and not self.svn_path_edit.text().strip():
            self.svn_path_edit.setText(find_default_svn())
        if not self.tp_path_edit.text().strip():
            self.tp_path_edit.setText(find_default_tortoiseproc())
        if not (self.svn_path_edit.text().strip() or self.tp_path_edit.text().strip()):
            ok = False; self.warn("Neither svn.exe nor TortoiseProc.exe found. Please set paths in Settings.")
        if not self.wc_roots:
            self.refresh_wc_roots()
        return ok

    def do_update(self):
        if not self.validate_paths(): return
        if not self.wc_roots:
            self.warn("No working copy root detected under selected folder."); return
        self.log_info("Running Update (all working copies)…")

        if self.use_svn_cli.isChecked() and self.svn_path_edit.text().strip():
            svn = self.svn_path_edit.text().strip()
            for root in self.wc_roots:
                code, out, err = run_cmd([svn, "update", "--depth", "infinity", root], cwd=root)
                self.log_proc(f"svn update [{root}]", code, out, err)
        elif self.tp_path_edit.text().strip():
            tp = self.tp_path_edit.text().strip()
            combined = "*".join(self.wc_roots)
            args = [tp, "/command:update", f"/path:{combined}", "/closeonend:1"]
            code, out, err = run_cmd(args)
            self.log_proc("TortoiseProc update [multi-path]", code, out, err)
        else:
            self.warn("No executable configured."); return

        self.log_info("Update finished.")
        self.prev_state = snapshot_tree(self.root_folder)

    def perform_commit_today_only(self):
        if not self.validate_paths(): return
        if not self.wc_roots:
            self.warn("No working copy root detected under selected folder."); return

        # Build per-WC today's list
        total_items = 0
        per_wc_items: Dict[str, Dict[str, str]] = {}
        for wc in self.wc_roots:
            items = self.changed_today.get(wc, {})
            # Filter out paths no longer under wc or not existing if not deletion
            clean: Dict[str, str] = {}
            for p, t in items.items():
                if not is_under(p, wc): continue
                if t in ('A', 'M'):
                    if not os.path.isfile(p):
                        clean[p] = 'D'
                    else:
                        try:
                            if datetime.fromtimestamp(os.path.getmtime(p)) >= self.today_zero:
                                clean[p] = t
                        except Exception:
                            continue
                elif t == 'D':
                    clean[p] = 'D'
            if clean:
                per_wc_items[wc] = clean
                total_items += len(clean)

        if total_items == 0:
            self.log_info("No items changed today. Skipping commit.")
            return

        if self.auto_update_before_commit.isChecked():
            self.do_update()

        message = self.compose_commit_message()

        if self.use_svn_cli.isChecked() and self.svn_path_edit.text().strip():
            svn = self.svn_path_edit.text().strip()
            for wc, items in per_wc_items.items():
                self.commit_with_svn_today_only(svn, wc, items, message)
        elif self.tp_path_edit.text().strip():
            tp = self.tp_path_edit.text().strip()
            for wc, items in per_wc_items.items():
                self.commit_with_tortoiseproc_today_only(tp, wc, items, message)
        else:
            self.warn("No executable configured for commit.")

    def chunk(self, seq: List[str], n: int) -> List[List[str]]:
        return [seq[i:i+n] for i in range(0, len(seq), n)]

    def commit_with_svn_today_only(self, svn_path: str, wc_root: str, items: Dict[str, str], message: str):
        self.log_info(f"[{wc_root}] Preparing 'today' commit (svn.exe)…")

        add_list = [p for p, t in items.items() if t == 'A' and os.path.isfile(p)]
        del_list = [p for p, t in items.items() if t == 'D']
        # Stage adds
        for chunk in self.chunk(add_list, 50):
            code, out, err = run_cmd([svn_path, "add", "--force"] + chunk, cwd=wc_root)
            self.log_proc(f"svn add [{wc_root}] (+{len(chunk)})", code, out, err)
        # Stage deletes
        for chunk in self.chunk(del_list, 50):
            code, out, err = run_cmd([svn_path, "rm", "--force"] + chunk, cwd=wc_root)
            self.log_proc(f"svn rm  [{wc_root}] (−{len(chunk)})", code, out, err)

        # Build commit target list (A/M/D)
        commit_targets = list(items.keys())
        if not commit_targets:
            self.log_info(f"[{wc_root}] Nothing to commit (today)."); return

        # Commit in chunks to avoid command-line limit
        for chunk in self.chunk(commit_targets, 80):
            args = [svn_path, "commit", "-m", message] + chunk
            code, out, err = run_cmd(args, cwd=wc_root, timeout=3600)
            self.log_proc(f"svn commit [{wc_root}] ({len(chunk)} paths)", code, out, err)
            if code == 0:
                self.log_success(f"[{wc_root}] Commit chunk complete.")
                for p in chunk:
                    self.changed_today.get(wc_root, {}).pop(p, None)
            else:
                self.log_warn(f"[{wc_root}] Commit chunk failed.")

    def commit_with_tortoiseproc_today_only(self, tp_path: str, wc_root: str, items: Dict[str, str], message: str):
        self.log_info(f"[{wc_root}] Preparing 'today' commit (TortoiseProc)…")
        svn = self.svn_path_edit.text().strip() if self.svn_path_edit.text().strip() else None
        add_list = [p for p, t in items.items() if t == 'A' and os.path.isfile(p)]
        del_list = [p for p, t in items.items() if t == 'D']
        if svn:
            for chunk in self.chunk(add_list, 50):
                code, out, err = run_cmd([svn, "add", "--force"] + chunk, cwd=wc_root)
                self.log_proc(f"svn add [{wc_root}] (+{len(chunk)})", code, out, err)
            for chunk in self.chunk(del_list, 50):
                code, out, err = run_cmd([svn, "rm", "--force"] + chunk, cwd=wc_root)
                self.log_proc(f"svn rm  [{wc_root}] (−{len(chunk)})", code, out, err)
        else:
            self.log_warn(f"[{wc_root}] svn.exe not configured; TortoiseProc will try to handle adds/removes.")

        targets = list(items.keys())
        if not targets:
            self.log_info(f"[{wc_root}] Nothing to commit (today)."); return

        for chunk in self.chunk(targets, 100):
            combined = "*".join(chunk)
            args = [
                tp_path, "/command:commit",
                f"/path:{combined}",
                f"/logmsg:{message}",
                "/notempfile",
                "/closeonend:1"
            ]
            code, out, err = run_cmd(args, cwd=wc_root)
            self.log_proc(f"TortoiseProc commit [{wc_root}] ({len(chunk)} paths)", code, out, err)
            if code == 0:
                self.log_success(f"[{wc_root}] Commit chunk triggered.")
                for p in chunk:
                    self.changed_today.get(wc_root, {}).pop(p, None)
            else:
                self.log_warn(f"[{wc_root}] Commit chunk failed or cancelled.")

    def compose_commit_message(self) -> str:
        prefix = (self.commit_prefix.text().strip() or "Auto-commit (Today)")
        user = getpass.getuser()
        return f"{prefix}: {human_time()} by {user} ({APP_NAME} {VERSION})"

    # --------------------------- Logging ---------------------------

    def log_info(self, msg: str): self.append_log(f"ℹ️  {human_time()}  {msg}")
    def log_warn(self, msg: str): self.append_log(f"⚠️  {human_time()}  {msg}")
    def log_success(self, msg: str): self.append_log(f"✅ {human_time()}  {msg}")

    def log_proc(self, title: str, code: int, out: str, err: str):
        self.append_log(f"▶ {title} -> exit {code}")
        if out: self.append_log(out)
        if err: self.append_log(f"stderr: {err}")

    def append_log(self, text: str):
        self.log.appendPlainText(text)
        self.log.verticalScrollBar().setValue(self.log.verticalScrollBar().maximum())

    def warn(self, text: str):
        QMessageBox.warning(self, APP_NAME, text)

# --------------------------- Entrypoint ---------------------------

def main():
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME); app.setOrganizationName(APP_ORG)
    app.setWindowIcon(make_app_icon())
    win = MainWindow(); win.show(); win.apply_bottom_right_position()
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()
