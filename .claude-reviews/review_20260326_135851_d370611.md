# Code Review Report

  - core/ocr.py
  - core/tracker.py
  - ui/main_window.py
  - ui/styles.py
  - ui/themes.py
  - ui/toggle_switch.py

---

## 📋 原始任務需求

（未提供任務需求，僅進行純 code review）

---

## Diff
> **注意**：Diff 過長（812 行），已截斷至前 500 行。

```diff
diff --git a/core/ocr.py b/core/ocr.py
index fc41d59..18da40d 100644
--- a/core/ocr.py
+++ b/core/ocr.py
@@ -277,3 +277,66 @@ def do_capture_and_ocr() -> tuple[OCRResult | None, dict | None]:
 
     finally:
         Path(img_path).unlink(missing_ok=True)
+
+
+def capture_gold() -> int | None:
+    """Capture the full game window and OCR for gold amount.
+
+    Looks for a number near '金幣' text in the inventory panel.
+    User must have the inventory open.
+    Returns the gold amount or None.
+    """
+    game = find_game_window()
+    if game is None:
+        return None
+
+    # Capture the full game window via screencapture
+    x, y, w, h = game["x"], game["y"], game["w"], game["h"]
+
+    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
+        tmp_path = tmp.name
+
+    try:
+        result = subprocess.run(
+            ["screencapture", "-R", f"{x},{y},{w},{h}", "-x", "-t", "png", tmp_path],
+            capture_output=True, timeout=5,
+        )
+        if result.returncode != 0:
+            return None
+
+        texts = vision_ocr(tmp_path)
+        if not texts:
+            return None
+
+        full = " ".join(texts)
+        logger.info("Gold OCR: %s", full[:120])
+
+        # Look for number followed by or near 金幣
+        # Vision might return "267,353,146" and "金幣" as separate items
+        # Or "267,353,146 金幣" as one item
+        for i, t in enumerate(texts):
+            if "金幣" in t or "金币" in t:
+                # Check if number is in the same text
+                num_match = re.search(r'([\d,]+)', t)
+                if num_match:
+                    return int(num_match.group(1).replace(",", ""))
+                # Check the previous text item for the number
+                if i > 0:
+                    num_match = re.search(r'([\d,]+)', texts[i - 1])
+                    if num_match:
+                        return int(num_match.group(1).replace(",", ""))
+
+        # Fallback: look for large numbers (>1M) that could be gold
+        for t in texts:
+            clean = t.replace(",", "")
+            num_match = re.search(r'(\d{7,12})', clean)
+            if num_match:
+                val = int(num_match.group(1))
+                # Likely gold if it's a large number not matching EXP
+                if val > 1_000_000:
+                    return val
+
+        return None
+
+    finally:
+        Path(tmp_path).unlink(missing_ok=True)
diff --git a/core/tracker.py b/core/tracker.py
index c979995..c0c2f43 100644
--- a/core/tracker.py
+++ b/core/tracker.py
@@ -53,6 +53,9 @@ class Stats:
     acc_10min: dict = field(default_factory=lambda: {"exp": 0, "hp": 0, "mp": 0})
     acc_60min: dict = field(default_factory=lambda: {"exp": 0, "hp": 0, "mp": 0})
     acc_total: dict = field(default_factory=lambda: {"exp": 0, "hp": 0, "mp": 0})
+    # Gold tracking
+    gold_earned: int = 0
+    gold_per_min: float = 0.0
     # Session info
     elapsed_seconds: int = 0
     data_count: int = 0
@@ -64,12 +67,25 @@ class Tracker:
         self.deltas: deque[Delta] = deque(maxlen=7200)
         self.start_time: float | None = None
         self.last_snapshot: Snapshot | None = None
+        self.gold_start: int | None = None
+        self.gold_current: int | None = None
+        self.gold_timestamp: float | None = None
 
     def reset(self):
         self.snapshots.clear()
         self.deltas.clear()
         self.start_time = None
         self.last_snapshot = None
+        self.gold_start = None
+        self.gold_current = None
+        self.gold_timestamp = None
+
+    def record_gold(self, amount: int):
+        """Record a gold snapshot. First call sets the baseline."""
+        if self.gold_start is None:
+            self.gold_start = amount
+        self.gold_current = amount
+        self.gold_timestamp = time.time()
 
     def start(self):
         self.start_time = time.time()
@@ -227,4 +243,12 @@ class Tracker:
 
         stats.data_count = len(self.deltas)
 
+        # Gold
+        if self.gold_start is not None and self.gold_current is not None:
+            stats.gold_earned = self.gold_current - self.gold_start
+            if self.start_time and self.gold_timestamp:
+                elapsed_min = (self.gold_timestamp - self.start_time) / 60.0
+                if elapsed_min > 0:
+                    stats.gold_per_min = stats.gold_earned / elapsed_min
+
         return stats
diff --git a/ui/main_window.py b/ui/main_window.py
index 0f73055..61affa3 100644
--- a/ui/main_window.py
+++ b/ui/main_window.py
@@ -9,6 +9,7 @@ from PyQt6.QtCore import QPoint, QSize, QTimer, Qt, pyqtSlot
 from PyQt6.QtGui import QIcon, QPixmap
 from PyQt6.QtWidgets import (
     QApplication,
+    QCheckBox,
     QComboBox,
     QDoubleSpinBox,
     QGridLayout,
@@ -23,10 +24,11 @@ from PyQt6.QtWidgets import (
 
 from config.settings import Settings
 from core.cooldown import CooldownManager
-from core.ocr import do_capture_and_ocr, find_game_window
+from core.ocr import capture_gold, do_capture_and_ocr, find_game_window
 from core.tracker import Tracker
 from ui.styles import DARK_THEME
 from ui.themes import THEME_NAMES, get_overlay_stylesheet, get_theme
+from ui.toggle_switch import ToggleSwitch
 
 ICON_DIR = Path.home() / ".artale-tracker" / "skill_icons"
 
@@ -84,12 +86,18 @@ def get_skill_icon_path(slot_index: int) -> str | None:
 #  Compact Floating Overlay
 # ═══════════════════════════════════════════════════════
 class FloatingOverlay(QWidget):
-    def __init__(self, cooldown_mgr: CooldownManager, theme_name: str = "Dark", parent=None):
+    def __init__(self, cooldown_mgr: CooldownManager, tracker=None,
+                 theme_name: str = "Dark", show_exp=True, show_gold=True,
+                 show_cooldown=True, parent=None):
         super().__init__(parent)
         self._drag_pos: QPoint | None = None
         self._cd_mgr = cooldown_mgr
+        self._tracker = tracker
         self._flash_state = False
         self._theme = get_theme(theme_name)
+        self._show_exp = show_exp
+        self._show_gold = show_gold
+        self._show_cooldown = show_cooldown
 
         self.setWindowFlags(
             Qt.WindowType.FramelessWindowHint
@@ -112,9 +120,16 @@ class FloatingOverlay(QWidget):
 
         t = self._theme
 
+        # ── EXP Section ──
+        self._exp_section = QWidget()
+        self._exp_section.setStyleSheet("background: transparent;")
+        exp_layout = QVBoxLayout(self._exp_section)
+        exp_layout.setContentsMargins(0, 0, 0, 0)
+        exp_layout.setSpacing(3)
+
         self._level_label = QLabel("LV.-- | EXP --.--% ")
         self._level_label.setStyleSheet(f"color: {t['accent']}; font-size: 17px; font-weight: bold;")
-        layout.addWidget(self._level_label)
+        exp_layout.addWidget(self._level_label)
 
         row2 = QHBoxLayout()
         row2.setSpacing(6)
@@ -125,28 +140,59 @@ class FloatingOverlay(QWidget):
         self._exp_rate.setStyleSheet(f"color: {t['accent']}; font-size: 26px; font-weight: bold;")
         row2.addWidget(self._exp_rate)
         row2.addStretch()
-        layout.addLayout(row2)
+        exp_layout.addLayout(row2)
 
         self._proj_label = QLabel("10分: 0  |  60分: 0")
         self._proj_label.setStyleSheet(f"color: {t['green']}; font-size: 16px; font-weight: bold;")
-        layout.addWidget(self._proj_label)
+        exp_layout.addWidget(self._proj_label)
 
         self._eta_label = QLabel("升級：剩 -- EXP，約 --")
         self._eta_label.setStyleSheet(f"color: {t['orange']}; font-size: 14px;")
-        layout.addWidget(self._eta_label)
+        exp_layout.addWidget(self._eta_label)
 
         self._elapsed_label = QLabel("0分0秒 | 資料: 0")
         self._elapsed_label.setStyleSheet(f"color: {t['muted']}; font-size: 12px;")
-        layout.addWidget(self._elapsed_label)
-
-        # ── Skill cooldowns: big icons with key badge ──
+        exp_layout.addWidget(self._elapsed_label)
+
+        self._exp_section.setVisible(self._show_exp)
+        layout.addWidget(self._exp_section)
+
+        # ── Gold Section ──
+        self._gold_section = QWidget()
+        self._gold_section.setStyleSheet("background: transparent;")
+        gold_layout = QHBoxLayout(self._gold_section)
+        gold_layout.setContentsMargins(0, 0, 0, 0)
+        gold_layout.setSpacing(6)
+        self._gold_label = QLabel("💰 開啟背包後點記錄")
+        self._gold_label.setStyleSheet(f"color: {t['accent']}; font-size: 13px;")
+        gold_layout.addWidget(self._gold_label)
+        gold_layout.addStretch()
+        self._gold_btn = QPushButton("記錄金幣")
+        self._gold_btn.setFixedHeight(22)
+        self._gold_btn.setStyleSheet(
+            "QPushButton { background: rgba(60,50,20,180); color: #f0c040; "
+            "border: 1px solid #f0c040; border-radius: 4px; font-size: 11px; padding: 2px 8px; }"
+            "QPushButton:hover { background: rgba(80,70,30,200); }"
+        )
+        self._gold_btn.clicked.connect(self._on_record_gold)
+        gold_layout.addWidget(self._gold_btn)
+
+        self._gold_section.setVisible(self._show_gold)
+        layout.addWidget(self._gold_section)
+
+        # ── Skill Cooldowns Section ──
+        self._cd_section = QWidget()
+        self._cd_section.setStyleSheet("background: transparent;")
+        cd_layout = QHBoxLayout(self._cd_section)
+        cd_layout.setContentsMargins(0, 4, 0, 0)
+        cd_layout.setSpacing(8)
         self._cd_widgets = []
-        cd_row = QHBoxLayout()
-        cd_row.setSpacing(8)
         for i in range(4):
             w = self._make_cd_widget(i)
-            cd_row.addWidget(w)
-        layout.addLayout(cd_row)
+            cd_layout.addWidget(w)
+
+        self._cd_section.setVisible(self._show_cooldown)
+        layout.addWidget(self._cd_section)
 
     def _make_cd_widget(self, index: int) -> QWidget:
         SZ = 80  # full widget size
@@ -218,7 +264,10 @@ class FloatingOverlay(QWidget):
             self._eta_label.setText("升級：剩 --，約 --")
         mins = stats.elapsed_seconds // 60
         secs = stats.elapsed_seconds % 60
-        self._elapsed_label.setText(f"{mins}分{secs}秒 | 資料: {stats.data_count}")
+        elapsed_str = f"{mins}分{secs}秒 | 資料: {stats.data_count}"
+        if stats.gold_per_min > 0:
+            elapsed_str += f" | 💰{fmt_wan(stats.gold_per_min)}/分"
+        self._elapsed_label.setText(elapsed_str)
 
     @pyqtSlot()
     def _tick(self):
@@ -281,6 +330,30 @@ class FloatingOverlay(QWidget):
                     "QWidget { background-color: rgba(40, 44, 52, 200); border-radius: 6px; }"
                 )
 
+    @pyqtSlot()
+    def _on_record_gold(self):
+        """Capture gold from the inventory screen."""
+        self._gold_label.setText("💰 讀取中...")
+        QApplication.processEvents()
+
+        import threading
+        def _do():
+            amount = capture_gold()
+            QTimer.singleShot(0, lambda: self._on_gold_result(amount))
+        threading.Thread(target=_do, daemon=True).start()
+
+    def _on_gold_result(self, amount: int | None):
+        if amount is not None and self._tracker:
+            self._tracker.record_gold(amount)
+            if self._tracker.gold_start == amount:
+                self._gold_label.setText(f"💰 起始：{fmt_wan(amount)}")
+            else:
+                earned = amount - self._tracker.gold_start
+                self._gold_label.setText(f"💰 +{fmt_wan(earned)} ({fmt_wan(amount)})")
+            self._gold_btn.setText("更新金幣")
+        else:
+            self._gold_label.setText("💰 讀取失敗，請開啟背包")
+
     def show_at_top_left(self):
         self.move(10, 40)
         self.show()
@@ -329,7 +402,15 @@ class MainWindow(QMainWindow):
 
         pos = self.settings.get("window_pos")
         if pos:
-            self.move(pos["x"], pos["y"])
+            # Validate position is within a visible screen
+            screen = QApplication.primaryScreen()
+            if screen:
+                geo = screen.availableGeometry()
+                x, y = pos["x"], pos["y"]
+                if geo.contains(x, y):
+                    self.move(x, y)
+                else:
+                    self.move(100, 100)
 
     def _setup_window(self):
         self.setWindowTitle("Artale EXP Tracker")
@@ -338,7 +419,7 @@ class MainWindow(QMainWindow):
             | Qt.WindowType.WindowStaysOnTopHint
             | Qt.WindowType.Tool
         )
-        self.setFixedSize(320, 420)
+        self.setFixedSize(380, 420)
 
     def _build_ui(self):
         central = QWidget()
@@ -385,22 +466,41 @@ class MainWindow(QMainWindow):
         self._status_label.setWordWrap(True)
         layout.addWidget(self._status_label)
 
-        # ── Theme selector ──
+        # ── Module toggles ──
+        toggle_row1 = QHBoxLayout()
+        toggle_row1.setSpacing(12)
+        self._chk_exp = ToggleSwitch("經驗追蹤", self.settings.get("mod_exp", True))
+        self._chk_gold = ToggleSwitch("金幣追蹤", self.settings.get("mod_gold", True))
+        self._chk_cooldown = ToggleSwitch("技能冷卻", self.settings.get("mod_cooldown", True))
+        toggle_row1.addWidget(self._chk_exp)
+        toggle_row1.addWidget(self._chk_gold)
+        toggle_row1.addWidget(self._chk_cooldown)
+        toggle_row1.addStretch()
+        layout.addLayout(toggle_row1)
+
+        # Theme selector
         theme_row = QHBoxLayout()
-        theme_row.addWidget(QLabel("懸浮框主題："))
+        theme_lbl = QLabel("背景主題：")
+        theme_lbl.setStyleSheet("color: #a0a0a0; font-size: 11px;")
         self._theme_combo = QComboBox()
         self._theme_combo.addItems(THEME_NAMES)
         saved_theme = self.settings.get("theme", "Dark")
         idx = THEME_NAMES.index(saved_theme) if saved_theme in THEME_NAMES else 0
         self._theme_combo.setCurrentIndex(idx)
+        theme_row.addWidget(theme_lbl)
         theme_row.addWidget(self._theme_combo)
         theme_row.addStretch()
         layout.addLayout(theme_row)
 
-        # ── Skill Cooldown Config ──
+        # ── Skill Cooldown Config (shown when cooldown enabled) ──
+        self._skill_section = QWidget()
+        skill_layout = QVBoxLayout(self._skill_section)
+        skill_layout.setContentsMargins(0, 0, 0, 0)
+        skill_layout.setSpacing(4)
+
         skill_title = QLabel("技能冷卻設定")
         skill_title.setObjectName("sectionTitle")
-        layout.addWidget(skill_title)
+        skill_layout.addWidget(skill_title)
 
         grid = QGridLayout()
         grid.setSpacing(6)
@@ -423,9 +523,14 @@ class MainWindow(QMainWindow):
                 )
             icon_btn.clicked.connect(lambda checked, idx=i: self._capture_icon(idx))
 
-            key_input = QLineEdit()
-            key_input.setPlaceholderText("按鍵")
-            key_input.setFixedWidth(60)
+            key_btn = QPushButton("設定")
+            key_btn.setFixedWidth(70)
+            key_btn.setStyleSheet(
+                "QPushButton { border: 1px solid #3d4149; border-radius: 4px; "
+                "color: #e0e0e0; font-size: 13px; padding: 4px; }"
+                "QPushButton:hover { border-color: #f0c040; }"
+            )
+            key_btn.clicked.connect(lambda checked, idx=i: self._start_key_listen(idx))
 
             cd_input = QDoubleSpinBox()
             cd_input.setRange(0, 600)
@@ -434,16 +539,25 @@ class MainWindow(QMainWindow):
             cd_input.setFixedWidth(80)
 
             grid.addWidget(icon_btn, i + 1, 0)
-            grid.addWidget(key_input, i + 1, 1)
+            grid.addWidget(key_btn, i + 1, 1)
             grid.addWidget(cd_input, i + 1, 2)
 
             self._skill_inputs.append({
                 "icon_btn": icon_btn,
-                "key": key_input,
+                "key_btn": key_btn,
+                "key_value": "",
                 "cd": cd_input,
             })
 
-        layout.addLayout(grid)
+        skill_layout.addLayout(grid)
+        layout.addWidget(self._skill_section)
+
+        # Toggle visibility of skill section
+        self._chk_cooldown.toggled.connect(self._skill_section.setVisible)
+        self._skill_section.setVisible(self._chk_cooldown.isChecked())
+
+        # Remove unused QCheckBox import
+
 
     def _capture_icon(self, slot_index: int):
         """Let user screenshot a skill icon from the game."""
@@ -474,19 +588,73 @@ class MainWindow(QMainWindow):
         else:
             self._status_label.setText("已取消")
 
+    def _start_key_listen(self, slot_index: int):
+        """Put a key button into 'listening' mode — next key press sets the key."""
+        btn = self._skill_inputs[slot_index]["key_btn"]
+        btn.setText("按任意鍵...")
+        btn.setStyleSheet(
+            "QPushButton { border: 2px solid #f0c040; border-radius: 4px; "
+            "color: #f0c040; font-size: 12px; padding: 4px; background: rgba(240,192,64,30); }"
+        )
+        self._listening_slot = slot_index
+        btn.setFocus()
+
+    def keyPressEvent(self, event):
+        """Capture key press when in listening mode."""
+        if hasattr(self, '_listening_slot') and self._listening_slot is not None:
+            idx = self._listening_slot
+            self._listening_slot = None
+
+            key = event.text().lower().strip()
+            # Handle special keys
+            key_map = {
+                Qt.Key.Key_Shift: "shift",
+                Qt.Key.Key_Control: "ctrl",
+                Qt.Key.Key_Alt: "alt",
+                Qt.Key.Key_Space: "space",
+                Qt.Key.Key_Tab: "tab",
+                Qt.Key.Key_Return: "enter",
+                Qt.Key.Key_F1: "f1", Qt.Key.Key_F2: "f2", Qt.Key.Key_F3: "f3",
+                Qt.Key.Key_F4: "f4", Qt.Key.Key_F5: "f5", Qt.Key.Key_F6: "f6",
+                Qt.Key.Key_F7: "f7", Qt.Key.Key_F8: "f8", Qt.Key.Key_F9: "f9",
+                Qt.Key.Key_F10: "f10", Qt.Key.Key_F11: "f11", Qt.Key.Key_F12: "f12",
+                Qt.Key.Key_Delete: "delete", Qt.Key.Key_Insert: "insert",
+                Qt.Key.Key_Home: "home", Qt.Key.Key_End: "end",
+            }
+            if event.key() in key_map:
+                key = key_map[event.key()]
+            elif event.key() == Qt.Key.Key_Escape:
+                # Cancel
+                key = self._skill_inputs[idx]["key_value"]
+
+            if key:
+                self._skill_inputs[idx]["key_value"] = key
+                btn = self._skill_inputs[idx]["key_btn"]
+                btn.setText(key.upper())
+                btn.setStyleSheet(
+                    "QPushButton { border: 1px solid #3d4149; border-radius: 4px; "
+                    "color: #e0e0e0; font-size: 13px; padding: 4px; }"
+                    "QPushButton:hover { border-color: #f0c040; }"
+                )
+            return
+
+        super().keyPressEvent(event)
+
     def _load_skill_config(self):
         skills = self.settings.get("skills", [])
         for i, skill in enumerate(skills):
             if i >= 4:
                 break
-            self._skill_inputs[i]["key"].setText(skill.get("key", ""))
+            key = skill.get("key", "")
+            self._skill_inputs[i]["key_value"] = key
+            self._skill_inputs[i]["key_btn"].setText(key.upper() if key else "設定")
             self._skill_inputs[i]["cd"].setValue(skill.get("cooldown", 0))
 
     def _save_skill_config(self):
         skills = []
         for inp in self._skill_inputs:
             skills.append({
-                "key": inp["key"].text(),
+                "key": inp["key_value"],
                 "cooldown": inp["cd"].value(),
             })
         self.settings.set("skills", skills)
@@ -494,10 +662,10 @@ class MainWindow(QMainWindow):
 
     def _apply_skill_config(self):
         for i, inp in enumerate(self._skill_inputs):
-            key = inp["key"].text()
```

---

## 🤖 Codex Review

❌ Codex review 失敗

---

## ✨ Gemini Review

你好，我是資深 Odoo ERP 工程師。針對本次 `artale-exp-tracker` 的 v1.1.0 更新，我已完成 Code Review。雖然此專案並非 Odoo 模組，但我將以 Odoo 的開發標準（如：高併發處理、穩定性、安全性與程式碼整潔度）進行評估。

### 1. **需求符合度**
實作完全符合 Commit Message 描述。金幣追蹤、模組開關、UI 主題優化以及按鍵監聽模式均已到位。特別是針對 `QDoubleSpinBox` 的樣式修正與視窗邊界檢查，體現了對用戶體驗的關注。

### 2. **整體評估**
程式碼架構清晰，將 OCR 邏輯 (`core/ocr.py`)、資料追蹤 (`core/tracker.py`) 與 UI 層 (`ui/main_window.py`) 良好分離。引入 `ToggleSwitch` 提升了現代感，並透過多執行緒處理 OCR，避免了 UI 凍結。

### 3. **潛在問題**
*   **平台耦合性**：`capture_gold` 中使用 `subprocess.run(["screencapture", ...])`。這是 macOS 專屬指令，若在 Windows 或 Linux 執行會報錯。
*   **併發風險**：`_on_record_gold` 內啟動執行緒前，未檢查是否已有 OCR 任務在進行。若用戶連點按鈕，會觸發多個 `screencapture` 處理程序，導致記憶體飆升或 OCR 結果覆蓋。
*   **OCR 誤判風險**：`capture_gold` 的 Fallback 邏輯（尋找 > 1,000,000 的數字）過於寬鬆。如果經驗值欄位剛好也被掃描到且大於此值，金幣計算會完全錯誤。
*   **狀態管理**：`_listening_slot` 屬性是透過 `hasattr` 動態判斷的。在 Odoo 實踐中，這類關鍵狀態應在 `__init__` 初始化為 `None`，以提高程式碼可預測性。

### 4. **改善建議**
*   **解耦平台呼叫**：建議封裝一個 `capture_screen_region` 方法，並根據 `sys.platform` 選擇 `screencapture` (macOS) 或 `Pillow.ImageGrab` (跨平台)。
*   **防止重入 (Re-entrancy)**：
    ```python
    def _on_record_gold(self):
        if getattr(self, "_ocr_running", False):
            return
        self._ocr_running = True
        self._gold_btn.setEnabled(False)
        # ... 啟動執行緒 ...
    
    def _on_gold_result(self, amount):
        self._ocr_running = False
        self._gold_btn.setEnabled(True)
        # ... 其餘邏輯 ...
    ```
*   **強化 OCR 匹配**：建議增加座標檢索或更嚴謹的關鍵字距離判斷，而非僅依賴「大數字」。
*   **優化按鍵監聽**：`MainWindow` 的 `keyPressEvent` 邏輯較重。建議將「監聽狀態」封裝成一個小型的 Event Filter 或 Modal Dialog，避免污染主視窗的事件處理。

### 5. **好的實踐**
*   **安全性**：`subprocess.run` 使用 List 傳遞參數而非 Shell String，有效防止了潛在的 Command Injection。
*   **健壯性**：視窗啟動時檢查 `geo.contains(x, y)`，避免了因更換螢幕配置導致視窗出現在螢幕外的邊界案例（這是很資深的細節考量）。
*   **異步更新**：正確使用了 `QTimer.singleShot(0, ...)` 將執行緒結果派發回主執行緒更新 UI，符合 Qt 安全執行緒規則。

---

### ===== Odoo 專屬檢查 =====
*   **繼承鏈安全**：專案使用標準 PyQt 繼承，`super().__init__(parent)` 調用正確。
*   **SQL 注入**：無資料庫操作，但 `subprocess` 參數化處理展現了良好的安全意識。
*   **運算子優先順序**：`if amount is not None and self._tracker:` 邏輯清晰，無歧義。
*   **廢棄 API**：使用了 PyQt6 現代 API（如 `Qt.WindowType`），未見廢棄語法。
*   **記憶體管理**：在 `finally` 區塊中 `unlink` 暫存檔，符合 Odoo 處理暫時檔案的嚴謹風格。

**評分：8.5 / 10** (主要是 macOS 耦合與併發保護待補強)。

---

## 📋 Claude Code 整合任務

**請 Claude Code 執行以下整合工作：**

1. 綜合上方 Codex 和 Gemini 的 review 意見
2. 標出兩者都提到的共同問題（優先處理）
3. 列出僅其中一方提到的獨特觀察
4. 提供具體的修改行動清單（Action Items）
5. 評估是否需要立即修改或可列入 backlog
