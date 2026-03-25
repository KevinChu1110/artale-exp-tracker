"""Dark theme QSS styles for Artale EXP Tracker."""

DARK_THEME = """
QWidget {
    background-color: #1a1d23;
    color: #e0e0e0;
    font-family: "Helvetica Neue", "Helvetica", "Arial";
    font-size: 13px;
}

QMainWindow {
    background-color: #1a1d23;
    border: 1px solid #2d3139;
    border-radius: 12px;
}

/* Title bar area */
#titleBar {
    background-color: #22262e;
    border-bottom: 1px solid #2d3139;
    padding: 8px;
}

#titleLabel {
    color: #f0c040;
    font-size: 15px;
    font-weight: bold;
}

/* Toolbar buttons */
QPushButton {
    background-color: #2d3139;
    color: #e0e0e0;
    border: 1px solid #3d4149;
    border-radius: 6px;
    padding: 6px 14px;
    font-size: 12px;
    font-weight: 500;
}

QPushButton:hover {
    background-color: #3d4149;
    border-color: #4d5159;
}

QPushButton:pressed {
    background-color: #4d5159;
}

QPushButton#startBtn {
    background-color: #2d5a2d;
    color: #80ff80;
    border-color: #3d6a3d;
}

QPushButton#startBtn:hover {
    background-color: #3d6a3d;
}

QPushButton#pauseBtn {
    background-color: #5a4a2d;
    color: #ffd080;
    border-color: #6a5a3d;
}

QPushButton#resetBtn {
    background-color: #5a2d2d;
    color: #ff8080;
    border-color: #6a3d3d;
}

/* Stat cards */
#statCard {
    background-color: #22262e;
    border: 1px solid #2d3139;
    border-radius: 8px;
    padding: 12px;
}

#rateCard {
    background-color: #22262e;
    border: 1px solid #d4a840;
    border-radius: 8px;
    padding: 10px;
}

/* Labels */
#sectionTitle {
    color: #f0c040;
    font-size: 14px;
    font-weight: bold;
}

#rateLabel {
    font-size: 11px;
    color: #a0a0a0;
}

#expValue {
    color: #f0c040;
    font-size: 20px;
    font-weight: bold;
}

#hpValue {
    color: #ff6b6b;
    font-size: 20px;
    font-weight: bold;
}

#mpValue {
    color: #6bc5ff;
    font-size: 20px;
    font-weight: bold;
}

#projectionText {
    color: #80ff80;
    font-size: 12px;
}

#levelUpText {
    color: #ffa060;
    font-size: 12px;
}

#infoText {
    color: #b0b0b0;
    font-size: 12px;
}

#timeText {
    color: #e0e0e0;
    font-size: 13px;
    font-weight: bold;
}

/* Accumulated stats */
#accLabel {
    color: #c0c0c0;
    font-size: 12px;
}

#accValue {
    font-size: 12px;
    font-weight: bold;
}

/* Recent entries list */
#recentList {
    background-color: #22262e;
    border: 1px solid #2d3139;
    border-radius: 4px;
    padding: 4px;
}

QListWidget {
    background-color: #22262e;
    border: none;
    color: #e0e0e0;
    font-size: 11px;
}

QListWidget::item {
    padding: 2px 4px;
    border-bottom: 1px solid #2d3139;
}

QListWidget::item:selected {
    background-color: #3d4149;
    color: #ff8080;
}

/* Scrollbar */
QScrollBar:vertical {
    background: #1a1d23;
    width: 6px;
}

QScrollBar::handle:vertical {
    background: #3d4149;
    border-radius: 3px;
    min-height: 20px;
}

/* Input fields */
QSpinBox, QLineEdit {
    background-color: #22262e;
    border: 1px solid #3d4149;
    border-radius: 4px;
    padding: 4px 8px;
    color: #e0e0e0;
    font-size: 12px;
}

QSpinBox:focus, QLineEdit:focus {
    border-color: #f0c040;
}

/* Compact mode toggle */
#compactToggle {
    background-color: transparent;
    border: none;
    color: #a0a0a0;
    font-size: 11px;
    padding: 2px;
}

#compactToggle:hover {
    color: #f0c040;
}

/* Status bar */
#statusBar {
    color: #808080;
    font-size: 11px;
    padding: 4px 8px;
    border-top: 1px solid #2d3139;
}
"""
