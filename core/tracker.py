import time
from collections import deque
from dataclasses import dataclass, field


@dataclass
class Snapshot:
    """A single OCR reading from the status bar."""
    timestamp: float
    level: int = 0
    exp_current: int = 0
    exp_percent: float = 0.0
    exp_total: int = 0        # total EXP needed for this level
    exp_remaining: int = 0    # remaining EXP to level up
    hp_current: int = 0
    hp_max: int = 0
    mp_current: int = 0
    mp_max: int = 0


@dataclass
class Delta:
    """Change between two consecutive readings."""
    timestamp: float
    exp_gained: int = 0
    hp_consumed: int = 0  # max - current change (potion usage indicator)
    mp_consumed: int = 0


@dataclass
class Stats:
    # Current state
    level: int = 0
    exp_current: int = 0
    exp_percent: float = 0.0
    exp_remaining: int = 0
    exp_total: int = 0
    hp_current: int = 0
    hp_max: int = 0
    mp_current: int = 0
    mp_max: int = 0
    # Rates
    exp_per_min: float = 0.0
    hp_per_min: float = 0.0  # HP consumption per min
    mp_per_min: float = 0.0  # MP consumption per min
    # Projections
    exp_10min: float = 0.0
    exp_60min: float = 0.0
    # Level up
    time_to_level: str = "--"
    # Accumulated within time windows
    acc_1min: dict = field(default_factory=lambda: {"exp": 0, "hp": 0, "mp": 0})
    acc_10min: dict = field(default_factory=lambda: {"exp": 0, "hp": 0, "mp": 0})
    acc_60min: dict = field(default_factory=lambda: {"exp": 0, "hp": 0, "mp": 0})
    acc_total: dict = field(default_factory=lambda: {"exp": 0, "hp": 0, "mp": 0})
    # Gold tracking
    gold_earned: int = 0
    gold_per_min: float = 0.0
    # Session info
    elapsed_seconds: int = 0
    data_count: int = 0


class Tracker:
    def __init__(self):
        self.snapshots: deque[Snapshot] = deque(maxlen=7200)
        self.deltas: deque[Delta] = deque(maxlen=7200)
        self.start_time: float | None = None
        self.last_snapshot: Snapshot | None = None
        self.gold_start: int | None = None
        self.gold_current: int | None = None
        self.gold_timestamp: float | None = None

    def reset(self):
        self.snapshots.clear()
        self.deltas.clear()
        self.start_time = None
        self.last_snapshot = None
        self.gold_start = None
        self.gold_current = None
        self.gold_timestamp = None

    def record_gold(self, amount: int):
        """Record a gold snapshot. First call sets the baseline."""
        if self.gold_start is None:
            self.gold_start = amount
        self.gold_current = amount
        self.gold_timestamp = time.time()

    def start(self):
        self.start_time = time.time()

    def add_reading(self, ocr_result) -> Delta | None:
        """Add a new OCR reading from the status bar.

        Args:
            ocr_result: OCRResult from core.ocr
        Returns:
            Delta if a valid change was detected, None otherwise.
        """
        now = time.time()
        if self.start_time is None:
            self.start_time = now

        snap = Snapshot(
            timestamp=now,
            level=ocr_result.level or 0,
            exp_current=ocr_result.exp_current or 0,
            exp_percent=ocr_result.exp_percent or 0.0,
            exp_total=ocr_result.exp_total or 0,
            exp_remaining=ocr_result.exp_remaining or 0,
            hp_current=ocr_result.hp_current or 0,
            hp_max=ocr_result.hp_max or 0,
            mp_current=ocr_result.mp_current or 0,
            mp_max=ocr_result.mp_max or 0,
        )

        delta = None
        if self.last_snapshot is not None:
            exp_gained = snap.exp_current - self.last_snapshot.exp_current

            # Handle level-up: EXP resets, so delta would be negative
            # In that case, we can estimate gain from percentage change
            if exp_gained < 0 and snap.level > self.last_snapshot.level:
                # Leveled up! Estimate EXP gained
                remaining_before = self.last_snapshot.exp_remaining
                exp_gained = remaining_before + snap.exp_current

            # Filter nonsensical values
            if exp_gained < 0 or exp_gained > 500_000_000:
                exp_gained = 0

            # HP/MP consumed (higher consumption = more potions used)
            hp_consumed = max(0, self.last_snapshot.hp_current - snap.hp_current)
            mp_consumed = max(0, self.last_snapshot.mp_current - snap.mp_current)

            if exp_gained > 0 or hp_consumed > 0 or mp_consumed > 0:
                delta = Delta(
                    timestamp=now,
                    exp_gained=exp_gained,
                    hp_consumed=hp_consumed,
                    mp_consumed=mp_consumed,
                )
                self.deltas.append(delta)

        self.snapshots.append(snap)
        self.last_snapshot = snap
        return delta

    def remove_delta(self, index: int):
        """Remove a delta entry (for correcting OCR errors)."""
        if 0 <= index < len(self.deltas):
            del self.deltas[index]

    def get_recent_deltas(self, count: int = 5) -> list[Delta]:
        return list(self.deltas)[-count:]

    def _sum_deltas_in_window(self, seconds: float) -> dict:
        now = time.time()
        cutoff = now - seconds
        total = {"exp": 0, "hp": 0, "mp": 0}
        for d in self.deltas:
            if d.timestamp >= cutoff:
                total["exp"] += d.exp_gained
                total["hp"] += d.hp_consumed
                total["mp"] += d.mp_consumed
        return total

    def _rate_per_minute(self) -> tuple[float, float, float]:
        """Calculate per-minute rates from all deltas."""
        if len(self.deltas) < 2:
            return 0.0, 0.0, 0.0

        total_exp = sum(d.exp_gained for d in self.deltas)
        total_hp = sum(d.hp_consumed for d in self.deltas)
        total_mp = sum(d.mp_consumed for d in self.deltas)

        first_ts = self.deltas[0].timestamp
        last_ts = self.deltas[-1].timestamp
        elapsed_min = (last_ts - first_ts) / 60.0

        if elapsed_min <= 0:
            return 0.0, 0.0, 0.0

        return (
            total_exp / elapsed_min,
            total_hp / elapsed_min,
            total_mp / elapsed_min,
        )

    def calculate_stats(self) -> Stats:
        stats = Stats()

        # Current state from last snapshot
        if self.last_snapshot:
            stats.level = self.last_snapshot.level
            stats.exp_current = self.last_snapshot.exp_current
            stats.exp_percent = self.last_snapshot.exp_percent
            stats.exp_remaining = self.last_snapshot.exp_remaining
            stats.exp_total = self.last_snapshot.exp_total
            stats.hp_current = self.last_snapshot.hp_current
            stats.hp_max = self.last_snapshot.hp_max
            stats.mp_current = self.last_snapshot.mp_current
            stats.mp_max = self.last_snapshot.mp_max

        if self.start_time:
            stats.elapsed_seconds = int(time.time() - self.start_time)

        if not self.deltas:
            return stats

        # Per-minute rates
        exp_rate, hp_rate, mp_rate = self._rate_per_minute()
        stats.exp_per_min = exp_rate
        stats.hp_per_min = hp_rate
        stats.mp_per_min = mp_rate

        # Projections
        stats.exp_10min = exp_rate * 10
        stats.exp_60min = exp_rate * 60

        # Time to level up
        if stats.exp_remaining > 0 and exp_rate > 0:
            minutes_left = stats.exp_remaining / exp_rate
            hours = int(minutes_left // 60)
            mins = int(minutes_left % 60)
            if hours > 0:
                stats.time_to_level = f"{hours}小時{mins}分"
            else:
                stats.time_to_level = f"{mins}分"

        # Accumulated within time windows
        stats.acc_1min = self._sum_deltas_in_window(60)
        stats.acc_10min = self._sum_deltas_in_window(600)
        stats.acc_60min = self._sum_deltas_in_window(3600)

        total = {"exp": 0, "hp": 0, "mp": 0}
        for d in self.deltas:
            total["exp"] += d.exp_gained
            total["hp"] += d.hp_consumed
            total["mp"] += d.mp_consumed
        stats.acc_total = total

        stats.data_count = len(self.deltas)

        # Gold
        if self.gold_start is not None and self.gold_current is not None:
            stats.gold_earned = self.gold_current - self.gold_start
            if self.start_time and self.gold_timestamp:
                elapsed_min = (self.gold_timestamp - self.start_time) / 60.0
                if elapsed_min > 0:
                    stats.gold_per_min = stats.gold_earned / elapsed_min

        return stats
