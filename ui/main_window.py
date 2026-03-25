"""Artale EXP Tracker — main control + compact floating overlay + skill cooldowns."""

import subprocess
import tempfile
from datetime import datetime
from pathlib import Path

from PyQt6.QtCore import QPoint, QSize, QTimer, Qt, pyqtSlot
from PyQt6.QtGui import QIcon, QPixmap
from PyQt6.QtWidgets import (
    QApplication,
    QComboBox,
    QDoubleSpinBox,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from config.settings import Settings
from core.cooldown import CooldownManager
from core.ocr import do_capture_and_ocr, find_game_window
from core.tracker import Tracker
from ui.styles import DARK_THEME
from ui.themes import THEME_NAMES, get_overlay_stylesheet, get_theme

ICON_DIR = Path.home() / ".artale-tracker" / "skill_icons"


def fmt(n: float) -> str:
    if isinstance(n, float):
        return f"{int(n):,}" if n == int(n) else f"{n:,.1f}"
    return f"{int(n):,}"


def fmt_wan(n: float) -> str:
    """Format large numbers in 萬(W) units: 2000000 → '200W'."""
    v = n if isinstance(n, (int, float)) else 0
    if abs(v) >= 10000:
        return f"{v / 10000:,.1f}W"
    return fmt(v)


def capture_skill_icon(slot_index: int) -> str | None:
    """Let user select a skill icon from screen. Returns saved path or None."""
    ICON_DIR.mkdir(parents=True, exist_ok=True)
    save_path = str(ICON_DIR / f"skill_{slot_index}.png")

    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
        tmp_path = tmp.name

    try:
        result = subprocess.run(
            ["screencapture", "-i", "-x", tmp_path],
            capture_output=True, timeout=60,
        )
        if result.returncode != 0 or not Path(tmp_path).exists():
            return None
        if Path(tmp_path).stat().st_size < 100:
            return None

        # Resize to 40x40 icon
        from PIL import Image
        img = Image.open(tmp_path)
        img = img.resize((40, 40), Image.LANCZOS)
        img.save(save_path)
        return save_path
    except Exception:
        return None
    finally:
        Path(tmp_path).unlink(missing_ok=True)


def get_skill_icon_path(slot_index: int) -> str | None:
    path = ICON_DIR / f"skill_{slot_index}.png"
    return str(path) if path.exists() else None


# ═══════════════════════════════════════════════════════
#  Compact Floating Overlay
# ═══════════════════════════════════════════════════════
class FloatingOverlay(QWidget):
    def __init__(self, cooldown_mgr: CooldownManager, theme_name: str = "Dark", parent=None):
        super().__init__(parent)
        self._drag_pos: QPoint | None = None
        self._cd_mgr = cooldown_mgr
        self._flash_state = False
        self._theme = get_theme(theme_name)

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setFixedWidth(380)
        self.setStyleSheet(get_overlay_stylesheet(theme_name))
        self._build_ui()

        self._tick_timer = QTimer(self)
        self._tick_timer.setInterval(200)
        self._tick_timer.timeout.connect(self._tick)
        self._tick_timer.start()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 10, 14, 10)
        layout.setSpacing(4)

        t = self._theme

        self._level_label = QLabel("LV.-- | EXP --.--% ")
        self._level_label.setStyleSheet(f"color: {t['accent']}; font-size: 17px; font-weight: bold;")
        layout.addWidget(self._level_label)

        row2 = QHBoxLayout()
        row2.setSpacing(6)
        lbl = QLabel("EXP/分")
        lbl.setStyleSheet(f"color: {t['muted']}; font-size: 14px;")
        row2.addWidget(lbl)
        self._exp_rate = QLabel("0")
        self._exp_rate.setStyleSheet(f"color: {t['accent']}; font-size: 26px; font-weight: bold;")
        row2.addWidget(self._exp_rate)
        row2.addStretch()
        layout.addLayout(row2)

        self._proj_label = QLabel("10分: 0  |  60分: 0")
        self._proj_label.setStyleSheet(f"color: {t['green']}; font-size: 16px; font-weight: bold;")
        layout.addWidget(self._proj_label)

        self._eta_label = QLabel("升級：剩 -- EXP，約 --")
        self._eta_label.setStyleSheet(f"color: {t['orange']}; font-size: 14px;")
        layout.addWidget(self._eta_label)

        self._elapsed_label = QLabel("0分0秒 | 資料: 0")
        self._elapsed_label.setStyleSheet(f"color: {t['muted']}; font-size: 12px;")
        layout.addWidget(self._elapsed_label)

        # ── Skill cooldowns: big icons with key badge ──
        self._cd_widgets = []
        cd_row = QHBoxLayout()
        cd_row.setSpacing(8)
        for i in range(4):
            w = self._make_cd_widget(i)
            cd_row.addWidget(w)
        layout.addLayout(cd_row)

    def _make_cd_widget(self, index: int) -> QWidget:
        SZ = 80  # full widget size
        ICON_SZ = 64  # icon fills most of the box
        container = QWidget()
        container.setFixedSize(SZ, SZ)
        container.setStyleSheet(
            "QWidget { background-color: rgba(30, 33, 40, 160); border-radius: 6px; }"
        )

        # Icon: nearly fills the box
        icon_label = QLabel(container)
        icon_label.setFixedSize(ICON_SZ, ICON_SZ)
        icon_label.move((SZ - ICON_SZ) // 2, 0)
        icon_label.setStyleSheet("background: transparent;")
        icon_label.setScaledContents(True)
        icon_path = get_skill_icon_path(index)
        if icon_path:
            icon_label.setPixmap(QPixmap(icon_path))

        # Key badge: top-right, visible
        key_label = QLabel(container)
        key_label.setFixedSize(22, 18)
        key_label.move(SZ - 24, 1)
        key_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        key_label.setStyleSheet(
            "background: rgba(0,0,0,180); color: #ccc; font-size: 11px; "
            "font-weight: bold; border-radius: 3px;"
        )

        # Cooldown text: centered over the icon
        cd_label = QLabel(container)
        cd_label.setFixedSize(SZ, 24)
        cd_label.move(0, SZ - 24)
        cd_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        cd_label.setStyleSheet(
            "color: #e0e0e0; font-size: 16px; font-weight: bold; "
            "background: rgba(0,0,0,140); border-bottom-left-radius: 6px; "
            "border-bottom-right-radius: 6px;"
        )

        self._cd_widgets.append({
            "container": container,
            "icon": icon_label,
            "key": key_label,
            "cd": cd_label,
        })
        return container

    def refresh_icons(self):
        for i, w in enumerate(self._cd_widgets):
            icon_path = get_skill_icon_path(i)
            if icon_path:
                w["icon"].setPixmap(QPixmap(icon_path))

    def update_stats(self, stats):
        lv = stats.level if stats.level else "--"
        pct = f"{stats.exp_percent:.2f}" if stats.exp_percent else "--"
        self._level_label.setText(f"LV.{lv} | EXP {pct}%")
        self._exp_rate.setText(fmt_wan(stats.exp_per_min))
        self._proj_label.setText(
            f"10分: {fmt_wan(stats.exp_10min)}  |  60分: {fmt_wan(stats.exp_60min)}"
        )
        if stats.exp_remaining > 0:
            self._eta_label.setText(
                f"升級：剩 {fmt_wan(stats.exp_remaining)}，約 {stats.time_to_level}"
            )
        else:
            self._eta_label.setText("升級：剩 --，約 --")
        mins = stats.elapsed_seconds // 60
        secs = stats.elapsed_seconds % 60
        self._elapsed_label.setText(f"{mins}分{secs}秒 | 資料: {stats.data_count}")

    @pyqtSlot()
    def _tick(self):
        self._elevate()
        self._update_cooldowns()

    def _update_cooldowns(self):
        self._cd_mgr.check_ready()
        self._cd_mgr.get_newly_ready()
        self._flash_state = not self._flash_state

        for i, slot in enumerate(self._cd_mgr.slots):
            if i >= len(self._cd_widgets):
                break
            w = self._cd_widgets[i]

            if not slot.enabled:
                w["key"].setText("")
                w["cd"].setText("")
                w["container"].setStyleSheet(
                    "QWidget { background-color: rgba(40, 44, 52, 200); border-radius: 6px; }"
                )
                continue

            # Show key badge
            w["key"].setText(slot.key.upper())

            remaining = slot.remaining
            if remaining > 0:
                # Cooling down
                w["cd"].setText(f"{remaining:.1f}s")
                w["cd"].setStyleSheet(
                    "color: #ff6b6b; font-size: 16px; font-weight: bold; background: transparent;"
                )
                w["container"].setStyleSheet(
                    "QWidget { background-color: rgba(80, 30, 30, 200); border-radius: 6px; }"
                )
            elif slot.last_used > 0:
                # Ready — flash
                if self._flash_state:
                    w["cd"].setText("OK!")
                    w["cd"].setStyleSheet(
                        "color: #80ff80; font-size: 16px; font-weight: bold; background: transparent;"
                    )
                    w["container"].setStyleSheet(
                        "QWidget { background-color: rgba(30, 80, 30, 220); border-radius: 6px; "
                        "border: 1px solid #80ff80; }"
                    )
                else:
                    w["cd"].setText("OK!")
                    w["cd"].setStyleSheet(
                        "color: #60cc60; font-size: 16px; font-weight: bold; background: transparent;"
                    )
                    w["container"].setStyleSheet(
                        "QWidget { background-color: rgba(30, 60, 30, 200); border-radius: 6px; }"
                    )
            else:
                w["cd"].setText("")
                w["container"].setStyleSheet(
                    "QWidget { background-color: rgba(40, 44, 52, 200); border-radius: 6px; }"
                )

    def show_at_top_left(self):
        self.move(10, 40)
        self.show()
        self._elevate()

    def _elevate(self):
        try:
            from AppKit import NSApp, NSFloatingWindowLevel
            for w in NSApp.windows():
                w.setLevel_(NSFloatingWindowLevel + 100)
                w.setHidesOnDeactivate_(False)
                w.setCollectionBehavior_(1 << 0 | 1 << 3)
        except Exception:
            pass

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()

    def mouseMoveEvent(self, event):
        if self._drag_pos and event.buttons() & Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_pos)

    def mouseReleaseEvent(self, event):
        self._drag_pos = None


# ═══════════════════════════════════════════════════════
#  Main Control Window
# ═══════════════════════════════════════════════════════
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.settings = Settings()
        self.tracker = Tracker()
        self.cooldown_mgr = CooldownManager()
        self._is_capturing = False
        self._overlay: FloatingOverlay | None = None
        self._drag_pos: QPoint | None = None

        self._setup_window()
        self._build_ui()
        self.setStyleSheet(DARK_THEME)
        self._setup_timers()
        self._load_skill_config()

        pos = self.settings.get("window_pos")
        if pos:
            self.move(pos["x"], pos["y"])

    def _setup_window(self):
        self.setWindowTitle("Artale EXP Tracker")
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setFixedSize(320, 420)

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(8)

        # Title + close
        title_row = QHBoxLayout()
        title = QLabel("Artale EXP Tracker")
        title.setObjectName("titleLabel")
        title_row.addWidget(title)
        title_row.addStretch()
        close_btn = QPushButton("X")
        close_btn.setObjectName("compactToggle")
        close_btn.setFixedSize(24, 24)
        close_btn.clicked.connect(self.close)
        title_row.addWidget(close_btn)
        layout.addLayout(title_row)

        # Game status
        self._game_label = QLabel("遊戲：偵測中...")
        self._game_label.setStyleSheet("color: #808080; font-size: 11px;")
        layout.addWidget(self._game_label)

        # Buttons
        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)
        self._start_btn = QPushButton("開始追蹤")
        self._start_btn.setObjectName("startBtn")
        self._start_btn.clicked.connect(self._on_start)
        btn_row.addWidget(self._start_btn)
        self._stop_btn = QPushButton("停止")
        self._stop_btn.setObjectName("resetBtn")
        self._stop_btn.clicked.connect(self._on_stop)
        self._stop_btn.setEnabled(False)
        btn_row.addWidget(self._stop_btn)
        layout.addLayout(btn_row)

        # Status
        self._status_label = QLabel("按「開始追蹤」會彈出懸浮框")
        self._status_label.setStyleSheet("color: #a0a0a0; font-size: 11px;")
        self._status_label.setWordWrap(True)
        layout.addWidget(self._status_label)

        # ── Theme selector ──
        theme_row = QHBoxLayout()
        theme_row.addWidget(QLabel("懸浮框主題："))
        self._theme_combo = QComboBox()
        self._theme_combo.addItems(THEME_NAMES)
        saved_theme = self.settings.get("theme", "Dark")
        idx = THEME_NAMES.index(saved_theme) if saved_theme in THEME_NAMES else 0
        self._theme_combo.setCurrentIndex(idx)
        theme_row.addWidget(self._theme_combo)
        theme_row.addStretch()
        layout.addLayout(theme_row)

        # ── Skill Cooldown Config ──
        skill_title = QLabel("技能冷卻設定")
        skill_title.setObjectName("sectionTitle")
        layout.addWidget(skill_title)

        grid = QGridLayout()
        grid.setSpacing(6)
        grid.addWidget(QLabel("圖示"), 0, 0)
        grid.addWidget(QLabel("按鍵"), 0, 1)
        grid.addWidget(QLabel("冷卻(秒)"), 0, 2)

        self._skill_inputs = []
        for i in range(4):
            icon_btn = QPushButton()
            icon_btn.setFixedSize(48, 48)
            icon_path = get_skill_icon_path(i)
            if icon_path:
                icon_btn.setIcon(QIcon(icon_path))
                icon_btn.setIconSize(QSize(40, 40))
            else:
                icon_btn.setText("📷")
                icon_btn.setStyleSheet(
                    "QPushButton { font-size: 20px; border: 1px dashed #3d4149; border-radius: 6px; }"
                )
            icon_btn.clicked.connect(lambda checked, idx=i: self._capture_icon(idx))

            key_input = QLineEdit()
            key_input.setPlaceholderText("按鍵")
            key_input.setFixedWidth(60)

            cd_input = QDoubleSpinBox()
            cd_input.setRange(0, 600)
            cd_input.setSuffix("s")
            cd_input.setDecimals(0)
            cd_input.setFixedWidth(80)

            grid.addWidget(icon_btn, i + 1, 0)
            grid.addWidget(key_input, i + 1, 1)
            grid.addWidget(cd_input, i + 1, 2)

            self._skill_inputs.append({
                "icon_btn": icon_btn,
                "key": key_input,
                "cd": cd_input,
            })

        layout.addLayout(grid)

    def _capture_icon(self, slot_index: int):
        """Let user screenshot a skill icon from the game."""
        self._status_label.setText(f"請框選技能{slot_index+1}的圖示...")
        self.hide()
        QApplication.processEvents()

        import threading

        def _do_capture():
            path = capture_skill_icon(slot_index)
            # Schedule UI update back on main thread
            QTimer.singleShot(0, lambda: self._on_icon_captured(slot_index, path))

        threading.Thread(target=_do_capture, daemon=True).start()

    def _on_icon_captured(self, slot_index: int, path: str | None):
        self.show()
        if path:
            btn = self._skill_inputs[slot_index]["icon_btn"]
            btn.setIcon(QIcon(path))
            btn.setIconSize(QSize(40, 40))
            btn.setText("")
            btn.setStyleSheet("QPushButton { border: 1px solid #3d4149; border-radius: 6px; }")
            self._status_label.setText(f"技能{slot_index+1}圖示已儲存")
            if self._overlay:
                self._overlay.refresh_icons()
        else:
            self._status_label.setText("已取消")

    def _load_skill_config(self):
        skills = self.settings.get("skills", [])
        for i, skill in enumerate(skills):
            if i >= 4:
                break
            self._skill_inputs[i]["key"].setText(skill.get("key", ""))
            self._skill_inputs[i]["cd"].setValue(skill.get("cooldown", 0))

    def _save_skill_config(self):
        skills = []
        for inp in self._skill_inputs:
            skills.append({
                "key": inp["key"].text(),
                "cooldown": inp["cd"].value(),
            })
        self.settings.set("skills", skills)
        self.settings.save()

    def _apply_skill_config(self):
        for i, inp in enumerate(self._skill_inputs):
            key = inp["key"].text()
            self.cooldown_mgr.configure_slot(
                i,
                name=key.upper(),  # use key as display name
                key=key,
                cooldown=inp["cd"].value(),
            )

    def _setup_timers(self):
        self._capture_timer = QTimer(self)
        interval = self.settings.get("ocr_interval", 5) * 1000
        self._capture_timer.setInterval(interval)
        self._capture_timer.timeout.connect(self._do_ocr_tick)

        self._ui_timer = QTimer(self)
        self._ui_timer.setInterval(1000)
        self._ui_timer.timeout.connect(self._refresh_overlay)

        self._game_timer = QTimer(self)
        self._game_timer.setInterval(3000)
        self._game_timer.timeout.connect(self._check_game)
        self._game_timer.start()
        self._check_game()

    @pyqtSlot()
    def _check_game(self):
        game = find_game_window()
        if game:
            self._game_label.setText("遊戲：已偵測 MapleStory Worlds")
            self._game_label.setStyleSheet("color: #80ff80; font-size: 11px;")
            if not self._is_capturing:
                self._start_btn.setEnabled(True)
        else:
            self._game_label.setText("遊戲：未偵測（請開啟遊戲）")
            self._game_label.setStyleSheet("color: #ff8080; font-size: 11px;")
            if not self._is_capturing:
                self._start_btn.setEnabled(False)

    @pyqtSlot()
    def _on_start(self):
        if self._is_capturing:
            return
        game = find_game_window()
        if not game:
            self._status_label.setText("找不到遊戲視窗！")
            return

        self._save_skill_config()
        self._apply_skill_config()

        self._is_capturing = True
        self.tracker.reset()
        self.tracker.start()
        self.cooldown_mgr.start()

        theme = self._theme_combo.currentText()
        self.settings.set("theme", theme)

        self._overlay = FloatingOverlay(self.cooldown_mgr, theme_name=theme)
        self._overlay.show_at_top_left()

        self._start_btn.setEnabled(False)
        self._stop_btn.setEnabled(True)
        self._status_label.setText(f"追蹤中... {datetime.now().strftime('%H:%M:%S')}")

        self._capture_timer.start()
        self._ui_timer.start()

    @pyqtSlot()
    def _on_stop(self):
        self._capture_timer.stop()
        self._ui_timer.stop()
        self._is_capturing = False
        self.cooldown_mgr.stop()

        if self._overlay:
            self._overlay.close()
            self._overlay = None

        self._start_btn.setEnabled(True)
        self._stop_btn.setEnabled(False)
        self._status_label.setText("已停止")

    @pyqtSlot()
    def _do_ocr_tick(self):
        result, game_info = do_capture_and_ocr()
        if game_info is None:
            self._status_label.setText("遊戲視窗消失了...")
            return
        if result and result.exp_current is not None:
            self.tracker.add_reading(result)
            self._status_label.setText(
                f"LV.{result.level or '?'} EXP={fmt(result.exp_current)} [{result.exp_percent}%]"
            )
        else:
            self._status_label.setText("狀態列被遮住，等待恢復...")

    @pyqtSlot()
    def _refresh_overlay(self):
        if not self._overlay:
            return
        stats = self.tracker.calculate_stats()
        self._overlay.update_stats(stats)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()

    def mouseMoveEvent(self, event):
        if self._drag_pos and event.buttons() & Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_pos)

    def mouseReleaseEvent(self, event):
        self._drag_pos = None

    def closeEvent(self, event):
        pos = self.pos()
        self.settings.set("window_pos", {"x": pos.x(), "y": pos.y()})
        self._save_skill_config()
        self.settings.save()
        self._capture_timer.stop()
        self._ui_timer.stop()
        self._game_timer.stop()
        self.cooldown_mgr.stop()
        if self._overlay:
            self._overlay.close()
        event.accept()
