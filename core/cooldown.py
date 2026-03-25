"""Skill cooldown tracker with macOS Quartz event tap for global key listening."""

import logging
import time
import threading
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class SkillSlot:
    name: str = ""
    key: str = ""
    cooldown: float = 0.0
    last_used: float = 0.0
    enabled: bool = False

    @property
    def remaining(self) -> float:
        if not self.enabled or self.cooldown <= 0:
            return 0.0
        elapsed = time.time() - self.last_used
        return max(0.0, self.cooldown - elapsed)

    @property
    def is_ready(self) -> bool:
        return self.enabled and self.remaining <= 0 and self.last_used > 0

    @property
    def progress(self) -> float:
        if not self.enabled or self.cooldown <= 0:
            return 1.0
        elapsed = time.time() - self.last_used
        return min(1.0, elapsed / self.cooldown)


# macOS virtual key code → key name
_VK_MAP = {
    0: "a", 1: "s", 2: "d", 3: "f", 4: "h", 5: "g", 6: "z", 7: "x",
    8: "c", 9: "v", 11: "b", 12: "q", 13: "w", 14: "e", 15: "r",
    16: "y", 17: "t", 18: "1", 19: "2", 20: "3", 21: "4", 22: "6",
    23: "5", 24: "=", 25: "9", 26: "7", 27: "-", 28: "8", 29: "0",
    31: "o", 32: "u", 34: "i", 35: "p", 37: "l", 38: "j", 40: "k",
    45: "n", 46: "m", 49: "space", 36: "enter", 48: "tab",
    51: "delete", 53: "esc",
    56: "shift", 58: "alt", 59: "ctrl",
    # F keys
    122: "f1", 120: "f2", 99: "f3", 118: "f4", 96: "f5", 97: "f6",
    98: "f7", 100: "f8", 101: "f9", 109: "f10", 103: "f11", 111: "f12",
    # Arrow keys
    123: "left", 124: "right", 125: "down", 126: "up",
    # Others
    114: "insert", 115: "home", 116: "pageup", 117: "delete",
    119: "end", 121: "pagedown",
}


class CooldownManager:
    """Manages 4 skill cooldown slots with Quartz event tap key listening."""

    def __init__(self):
        self.slots: list[SkillSlot] = [SkillSlot() for _ in range(4)]
        self._running = False
        self._tap = None
        self._loop_source = None
        self._thread: threading.Thread | None = None
        self._newly_ready: set[int] = set()

    def configure_slot(self, index: int, name: str, key: str, cooldown: float):
        if 0 <= index < 4:
            slot = self.slots[index]
            slot.name = name
            slot.key = key.lower().strip()
            slot.cooldown = cooldown
            slot.enabled = bool(name and key and cooldown > 0)
            slot.last_used = 0.0

    def start(self):
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._run_listener, daemon=True)
        self._thread.start()

    def stop(self):
        self._running = False
        if self._loop_source:
            try:
                import Quartz
                Quartz.CFRunLoopStop(Quartz.CFRunLoopGetCurrent())
            except Exception:
                pass
        self._tap = None
        self._loop_source = None

    def get_newly_ready(self) -> list[int]:
        result = list(self._newly_ready)
        self._newly_ready.clear()
        return result

    def check_ready(self):
        for i, slot in enumerate(self.slots):
            if slot.enabled and slot.last_used > 0:
                elapsed = time.time() - slot.last_used
                if slot.cooldown - 1.5 < elapsed <= slot.cooldown + 0.5:
                    if i not in self._newly_ready:
                        self._newly_ready.add(i)

    def _run_listener(self):
        """Run a Quartz event tap in a background thread."""
        try:
            import Quartz

            def callback(proxy, event_type, event, refcon):
                if event_type == Quartz.kCGEventKeyDown:
                    keycode = Quartz.CGEventGetIntegerValueField(
                        event, Quartz.kCGKeyboardEventKeycode
                    )
                    key_name = _VK_MAP.get(keycode, "")
                    if key_name:
                        self._on_key(key_name)
                return event

            # Create event tap — observe key down events
            tap = Quartz.CGEventTapCreate(
                Quartz.kCGSessionEventTap,
                Quartz.kCGHeadInsertEventTap,
                Quartz.kCGEventTapOptionListenOnly,  # passive, don't block
                Quartz.CGEventMaskBit(Quartz.kCGEventKeyDown),
                callback,
                None,
            )

            if tap is None:
                logger.error(
                    "Failed to create event tap. "
                    "Grant Accessibility permission: "
                    "System Settings → Privacy & Security → Accessibility → enable Terminal/Python"
                )
                return

            self._tap = tap
            loop_source = Quartz.CFMachPortCreateRunLoopSource(None, tap, 0)
            self._loop_source = loop_source

            run_loop = Quartz.CFRunLoopGetCurrent()
            Quartz.CFRunLoopAddSource(run_loop, loop_source, Quartz.kCFRunLoopCommonModes)
            Quartz.CGEventTapEnable(tap, True)

            logger.info("Quartz key listener started")

            # Run until stopped
            while self._running:
                Quartz.CFRunLoopRunInMode(Quartz.kCFRunLoopDefaultMode, 0.5, False)

            logger.info("Quartz key listener stopped")

        except Exception as e:
            logger.error("Key listener failed: %s", e)

    def _on_key(self, key_name: str):
        if not self._running:
            return
        now = time.time()
        for slot in self.slots:
            if slot.enabled and slot.key == key_name:
                if slot.last_used == 0 or slot.remaining <= 0:
                    slot.last_used = now
                    logger.debug("Skill '%s' used (key=%s, cd=%.1fs)", slot.name, key_name, slot.cooldown)
