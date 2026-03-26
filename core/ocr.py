import logging
import re
import subprocess
import tempfile
from dataclasses import dataclass

from core.exp_table import guess_level_from_exp
from pathlib import Path

from PIL import Image

logger = logging.getLogger(__name__)

try:
    import Quartz
    from Foundation import NSURL
    import Vision
    HAS_VISION = True
except ImportError:
    HAS_VISION = False
    logger.warning("macOS Vision framework not available")


@dataclass
class OCRResult:
    level: int | None = None
    exp_current: int | None = None
    exp_percent: float | None = None
    exp_total: int | None = None
    exp_remaining: int | None = None
    hp_current: int | None = None
    hp_max: int | None = None
    mp_current: int | None = None
    mp_max: int | None = None
    raw_text: str = ""


def find_game_window() -> dict | None:
    """Find the MapleStory Worlds window bounds."""
    if not HAS_VISION:
        return None

    windows = Quartz.CGWindowListCopyWindowInfo(
        Quartz.kCGWindowListOptionOnScreenOnly,
        Quartz.kCGNullWindowID
    )

    for w in windows:
        owner = w.get("kCGWindowOwnerName", "")
        title = w.get("kCGWindowName", "")
        bounds = w.get("kCGWindowBounds", {})

        if "MapleStory" in owner or "MapleStory" in title:
            return {
                "x": int(bounds.get("X", 0)),
                "y": int(bounds.get("Y", 0)),
                "w": int(bounds.get("Width", 0)),
                "h": int(bounds.get("Height", 0)),
            }
    return None


def capture_screen_region(region: dict) -> Image.Image | None:
    """Capture a screen region using macOS screencapture -R."""
    if not region:
        return None

    x, y, w, h = region["x"], region["y"], region["w"], region["h"]

    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
        tmp_path = tmp.name

    try:
        result = subprocess.run(
            ["screencapture", "-R", f"{x},{y},{w},{h}", "-x", "-t", "png", tmp_path],
            capture_output=True,
            timeout=5,
        )
        if result.returncode == 0 and Path(tmp_path).exists():
            img = Image.open(tmp_path)
            img.load()
            return img
    except (subprocess.TimeoutExpired, FileNotFoundError) as e:
        logger.error("Screen capture failed: %s", e)
    finally:
        Path(tmp_path).unlink(missing_ok=True)

    return None


def capture_game_statusbar() -> tuple[str | None, dict | None]:
    """Auto-detect game window and capture the bottom status bar.

    Returns: (image_path, game_window_info) — path is a temp PNG file.
    """
    game = find_game_window()
    if game is None:
        return None, None

    bar_height = 100  # bottom 100px captures the full status bar
    x = game["x"]
    y = game["y"] + game["h"] - bar_height
    w = game["w"]
    h = bar_height

    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
        tmp_path = tmp.name

    try:
        result = subprocess.run(
            ["screencapture", "-R", f"{x},{y},{w},{h}", "-x", "-t", "png", tmp_path],
            capture_output=True,
            timeout=5,
        )
        if result.returncode == 0 and Path(tmp_path).exists():
            return tmp_path, game
    except (subprocess.TimeoutExpired, FileNotFoundError) as e:
        logger.error("Screen capture failed: %s", e)

    Path(tmp_path).unlink(missing_ok=True)
    return None, None


def vision_ocr(image_path: str) -> list[str]:
    """Run macOS Vision OCR on an image file.

    Returns a list of recognized text strings, sorted by confidence.
    """
    if not HAS_VISION:
        return []

    url = NSURL.fileURLWithPath_(image_path)
    source = Quartz.CGImageSourceCreateWithURL(url, None)
    if source is None:
        return []

    cg_image = Quartz.CGImageSourceCreateImageAtIndex(source, 0, None)
    if cg_image is None:
        return []

    request = Vision.VNRecognizeTextRequest.alloc().init()
    request.setRecognitionLevel_(Vision.VNRequestTextRecognitionLevelAccurate)
    request.setUsesLanguageCorrection_(False)

    handler = Vision.VNImageRequestHandler.alloc().initWithCGImage_options_(cg_image, None)
    success, error = handler.performRequests_error_([request], None)

    if not success:
        logger.error("Vision OCR failed: %s", error)
        return []

    texts = []
    for obs in request.results():
        candidate = obs.topCandidates_(1)
        if candidate:
            texts.append(candidate[0].string())

    return texts


def parse_vision_results(texts: list[str]) -> OCRResult:
    """Parse Vision OCR results into structured data.

    Vision returns each text region separately. Handles multiple formats:

    Format A (status bar with labels):
        ['LV.', 'CapooCat', 'P[4483/5945]', 'MP[1687/4224]', 'EXP 159463281|74.53% ]']

    Format B (EXP bar with current/total):
        ['49,108,681,137', '1,137', '36.94%(1,044,230/2,827,108)']
        → percent=36.94, current=1,044,230, total=2,827,108
    """
    result = OCRResult(raw_text=" | ".join(texts))

    full_text = " ".join(texts)
    # Remove commas in numbers for easier parsing
    clean = full_text.replace(",", "")

    # --- Level ---
    # Try OCR first
    lv_match = re.search(r'LV\.?\s*(\d{2,3})', clean, re.IGNORECASE)
    if lv_match:
        result.level = int(lv_match.group(1))

    # --- EXP Format A: "EXP 159463281|74.53%" or "EXP.159463281[74.53%]" ---
    exp_a = re.search(
        r'E?X?P\.?\s*(\d{5,12})\s*[\[|\(|]?\s*(\d{1,3})[.,](\d{1,2})\s*%',
        clean
    )
    if exp_a:
        result.exp_current = int(exp_a.group(1))
        result.exp_percent = float(f"{exp_a.group(2)}.{exp_a.group(3)}")

    # --- EXP Format B: "36.94%(1044230/2827108)" ---
    if result.exp_current is None:
        exp_b = re.search(
            r'(\d{1,3})[.,](\d{1,2})%\s*[\(\[]?\s*(\d+)\s*/\s*(\d+)',
            clean
        )
        if exp_b:
            result.exp_percent = float(f"{exp_b.group(1)}.{exp_b.group(2)}")
            result.exp_current = int(exp_b.group(3))
            result.exp_total = int(exp_b.group(4))
            result.exp_remaining = result.exp_total - result.exp_current

    # --- EXP Format C: "36.94%(1044230|2827108)" with | instead of / ---
    if result.exp_current is None:
        exp_c = re.search(
            r'(\d{1,3})[.,](\d{1,2})%\s*[\(\[]?\s*(\d+)\s*[|]\s*(\d+)',
            clean
        )
        if exp_c:
            result.exp_percent = float(f"{exp_c.group(1)}.{exp_c.group(2)}")
            result.exp_current = int(exp_c.group(3))
            result.exp_total = int(exp_c.group(4))
            result.exp_remaining = result.exp_total - result.exp_current

    # Calculate total/remaining if we have current+percent but not total
    if result.exp_current and result.exp_percent and 0 < result.exp_percent < 100:
        if result.exp_total is None:
            result.exp_total = int(result.exp_current / (result.exp_percent / 100.0))
            result.exp_remaining = result.exp_total - result.exp_current

    # --- HP & MP ---
    # Search MP first (has distinct "M" prefix), then HP (Vision often drops "H")
    mp_match = re.search(r'MP\s*[\[\(]\s*(\d+)\s*/\s*(\d+)', clean)
    if mp_match:
        result.mp_current = int(mp_match.group(1))
        result.mp_max = int(mp_match.group(2))

    # HP: look for "HP[" or just "P[" but NOT "MP["
    # Use negative lookbehind to avoid matching MP
    hp_match = re.search(r'(?<!M)P\s*[\[\(]\s*(\d+)\s*/\s*(\d+)', clean)
    if hp_match:
        result.hp_current = int(hp_match.group(1))
        result.hp_max = int(hp_match.group(2))

    # --- Guess level from EXP table if OCR didn't read it ---
    if result.level is None and result.exp_current and result.exp_percent:
        result.level = guess_level_from_exp(result.exp_current, result.exp_percent)

    return result


def do_capture_and_ocr() -> tuple[OCRResult | None, dict | None]:
    """Full pipeline: auto-detect game → capture status bar → Vision OCR → parse."""
    img_path, game_info = capture_game_statusbar()
    if img_path is None:
        return None, game_info

    try:
        # Save debug copy
        debug_dir = Path.home() / ".artale-tracker"
        debug_dir.mkdir(parents=True, exist_ok=True)
        import shutil
        shutil.copy2(img_path, str(debug_dir / "debug_statusbar.png"))

        # Run Vision OCR
        texts = vision_ocr(img_path)

        if not texts:
            logger.warning("Vision OCR returned no results")
            return None, game_info

        result = parse_vision_results(texts)

        if result.exp_current and result.exp_percent:
            logger.info(
                "OCR OK: LV=%s EXP=%s [%.2f%%] HP=%s/%s MP=%s/%s",
                result.level, result.exp_current, result.exp_percent,
                result.hp_current, result.hp_max, result.mp_current, result.mp_max,
            )
        else:
            logger.info("OCR partial: %s", result.raw_text[:80])

        return result, game_info

    finally:
        Path(img_path).unlink(missing_ok=True)


def capture_gold() -> int | None:
    """Capture the full game window and OCR for gold amount.

    Looks for a number near '金幣' text in the inventory panel.
    User must have the inventory open.
    Returns the gold amount or None.
    """
    game = find_game_window()
    if game is None:
        return None

    # Capture the full game window via screencapture
    x, y, w, h = game["x"], game["y"], game["w"], game["h"]

    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
        tmp_path = tmp.name

    try:
        result = subprocess.run(
            ["screencapture", "-R", f"{x},{y},{w},{h}", "-x", "-t", "png", tmp_path],
            capture_output=True, timeout=5,
        )
        if result.returncode != 0:
            return None

        texts = vision_ocr(tmp_path)
        if not texts:
            return None

        full = " ".join(texts)
        logger.info("Gold OCR: %s", full[:120])

        # Strategy 1: find "金幣" text and get the number near it
        for i, t in enumerate(texts):
            if "金幣" in t or "金币" in t:
                num_match = re.search(r'([\d,]+)', t)
                if num_match and len(num_match.group(1)) > 3:
                    return int(num_match.group(1).replace(",", ""))
                if i > 0:
                    num_match = re.search(r'([\d,]+)', texts[i - 1])
                    if num_match:
                        return int(num_match.group(1).replace(",", ""))

        # Strategy 2: find numbers WITH commas (gold format: 267,493,263)
        # This distinguishes gold from EXP (which has no commas)
        for t in texts:
            comma_match = re.search(r'(\d{1,3}(?:,\d{3}){2,})', t)
            if comma_match:
                val = int(comma_match.group(1).replace(",", ""))
                if val > 100_000:  # reasonable gold amount
                    logger.info("Gold found (comma format): %s -> %d", comma_match.group(1), val)
                    return val

        return None

    finally:
        Path(tmp_path).unlink(missing_ok=True)
