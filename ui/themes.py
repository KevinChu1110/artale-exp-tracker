"""Overlay color themes."""

THEMES = {
    "Dark": {
        "bg": "rgba(15, 17, 22, 180)",
        "accent": "#f0c040",      # gold
        "text": "#e0e0e0",
        "green": "#80ff80",
        "orange": "#ffa060",
        "muted": "#808080",
        "skill_bg": "rgba(30, 33, 40, 160)",
        "cd_bg": "rgba(0,0,0,140)",
    },
    "Ocean": {
        "bg": "rgba(10, 20, 35, 185)",
        "accent": "#4fc3f7",      # light blue
        "text": "#e0e8f0",
        "green": "#69f0ae",
        "orange": "#ffb74d",
        "muted": "#78909c",
        "skill_bg": "rgba(15, 30, 50, 160)",
        "cd_bg": "rgba(0,10,30,150)",
    },
    "Crimson": {
        "bg": "rgba(25, 12, 15, 185)",
        "accent": "#ff5252",      # red
        "text": "#f0e0e0",
        "green": "#b9f6ca",
        "orange": "#ffcc80",
        "muted": "#8d6e63",
        "skill_bg": "rgba(40, 20, 25, 160)",
        "cd_bg": "rgba(20,0,0,150)",
    },
    "Forest": {
        "bg": "rgba(12, 22, 15, 185)",
        "accent": "#66bb6a",      # green
        "text": "#e0f0e0",
        "green": "#c5e1a5",
        "orange": "#ffe082",
        "muted": "#78897a",
        "skill_bg": "rgba(20, 35, 25, 160)",
        "cd_bg": "rgba(0,15,0,150)",
    },
    "Glass": {
        "bg": "rgba(20, 20, 20, 120)",
        "accent": "#ffffff",      # white
        "text": "#f0f0f0",
        "green": "#a5d6a7",
        "orange": "#ffcc80",
        "muted": "#9e9e9e",
        "skill_bg": "rgba(30, 30, 30, 100)",
        "cd_bg": "rgba(0,0,0,100)",
    },
}

THEME_NAMES = list(THEMES.keys())


def get_overlay_stylesheet(theme_name: str) -> str:
    t = THEMES.get(theme_name, THEMES["Dark"])
    return f"""
        QWidget {{
            background-color: {t['bg']};
            color: {t['text']};
            font-family: "Helvetica Neue", "Helvetica";
            font-size: 14px;
            border-radius: 10px;
        }}
    """


def get_theme(name: str) -> dict:
    return THEMES.get(name, THEMES["Dark"])
