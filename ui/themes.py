"""Overlay background themes — primarily changes background color/opacity."""

THEMES = {
    "Dark": {
        "bg": "rgba(15, 17, 22, 200)",
        "skill_bg": "rgba(30, 33, 40, 180)",
    },
    "Ocean": {
        "bg": "rgba(8, 22, 45, 200)",
        "skill_bg": "rgba(12, 30, 55, 180)",
    },
    "Crimson": {
        "bg": "rgba(35, 12, 15, 200)",
        "skill_bg": "rgba(45, 20, 25, 180)",
    },
    "Forest": {
        "bg": "rgba(10, 28, 15, 200)",
        "skill_bg": "rgba(15, 38, 22, 180)",
    },
    "Glass": {
        "bg": "rgba(20, 20, 20, 110)",
        "skill_bg": "rgba(30, 30, 30, 90)",
    },
}

# Shared text colors (same for all themes — always readable on dark bg)
TEXT_COLORS = {
    "accent": "#f0c040",
    "text": "#e0e0e0",
    "green": "#80ff80",
    "orange": "#ffa060",
    "muted": "#808080",
}

THEME_NAMES = list(THEMES.keys())


def get_overlay_stylesheet(theme_name: str) -> str:
    t = THEMES.get(theme_name, THEMES["Dark"])
    return f"""
        QWidget {{
            background-color: {t['bg']};
            color: #e0e0e0;
            font-family: "Helvetica Neue", "Helvetica";
            font-size: 14px;
            border-radius: 10px;
        }}
    """


def get_theme(name: str) -> dict:
    """Returns merged theme: background from theme + shared text colors."""
    bg = THEMES.get(name, THEMES["Dark"])
    return {**bg, **TEXT_COLORS}
