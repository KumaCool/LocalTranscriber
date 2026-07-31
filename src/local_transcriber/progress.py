from __future__ import annotations

import math
import time
from collections.abc import Callable
from dataclasses import dataclass


@dataclass(frozen=True)
class ProgressEstimate:
    progress_percent: float
    processed_units: float
    total_units: float
    eta_low_seconds: int | None
    eta_high_seconds: int | None
    confidence: str


class ProgressEstimator:
    """Estimate weighted progress from real upstream work-unit callbacks."""

    def __init__(
        self,
        *,
        clock: Callable[[], float] = time.monotonic,
        minimum_observation_seconds: float = 3.0,
        stall_seconds: float = 30.0,
    ) -> None:
        self._clock = clock
        self._minimum_observation_seconds = minimum_observation_seconds
        self._stall_seconds = stall_seconds
        self._started_at: float | None = None
        self._last_update_at: float | None = None
        self._last = ProgressEstimate(15.0, 0.0, 0.0, None, None, "calculating")
        self._smoothed_rate: float | None = None
        self._previous_units = 0.0

    def observe(self, current: float, total: float) -> ProgressEstimate:
        if not all(math.isfinite(value) for value in (current, total)):
            return self.current()
        if total <= 0 or current < 0 or current > total or current < self._previous_units:
            return self.current()

        now = self._clock()
        if self._started_at is None:
            self._started_at = now
            self._last_update_at = now
            self._previous_units = current
            self._last = ProgressEstimate(
                15.0 + 80.0 * current / total,
                current,
                total,
                None,
                None,
                "calculating",
            )
            return self._last

        elapsed = now - self._started_at
        delta_time = now - (self._last_update_at or self._started_at)
        delta_units = current - self._previous_units
        if delta_units > 0 and delta_time > 0:
            rate = delta_units / delta_time
            self._smoothed_rate = (
                rate if self._smoothed_rate is None else 0.35 * rate + 0.65 * self._smoothed_rate
            )
            self._last_update_at = now
            self._previous_units = current

        low: int | None = None
        high: int | None = None
        confidence = "calculating"
        if elapsed >= self._minimum_observation_seconds and self._smoothed_rate:
            remaining = max(0.0, total - current) / self._smoothed_rate
            low = max(0, math.floor(remaining * 0.8))
            high = max(low, math.ceil(remaining * 1.25))
            confidence = "normal"

        self._last = ProgressEstimate(
            min(95.0, 15.0 + 80.0 * current / total),
            current,
            total,
            low,
            high,
            confidence,
        )
        return self._last

    def current(self) -> ProgressEstimate:
        if self._last_update_at is None:
            return self._last
        stalled_for = self._clock() - self._last_update_at
        if stalled_for < self._stall_seconds or self._last.eta_high_seconds is None:
            return self._last
        widened_high = max(
            self._last.eta_high_seconds,
            math.ceil(self._last.eta_high_seconds * 1.75 + stalled_for),
        )
        return ProgressEstimate(
            self._last.progress_percent,
            self._last.processed_units,
            self._last.total_units,
            self._last.eta_low_seconds,
            widened_high,
            "low",
        )
