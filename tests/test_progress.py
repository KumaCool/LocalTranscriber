from __future__ import annotations

from local_transcriber.progress import ProgressEstimator


class FakeClock:
    def __init__(self) -> None:
        self.value = 0.0

    def __call__(self) -> float:
        return self.value

    def advance(self, seconds: float) -> None:
        self.value += seconds


def test_estimator_maps_real_units_to_weighted_progress_and_eta_range() -> None:
    clock = FakeClock()
    estimator = ProgressEstimator(clock=clock, minimum_observation_seconds=2)

    estimator.observe(0, 10)
    clock.advance(5)
    estimate = estimator.observe(5, 10)

    assert estimate.progress_percent == 55.0
    assert estimate.processed_units == 5
    assert estimate.total_units == 10
    assert estimate.eta_low_seconds <= 5 <= estimate.eta_high_seconds
    assert estimate.confidence == "normal"


def test_estimator_waits_for_enough_observation_and_rejects_invalid_or_backward_units() -> None:
    clock = FakeClock()
    estimator = ProgressEstimator(clock=clock, minimum_observation_seconds=3)

    initial = estimator.observe(2, 10)
    clock.advance(1)
    early = estimator.observe(3, 10)
    backward = estimator.observe(1, 10)
    invalid = estimator.observe(5, 0)

    assert initial.eta_low_seconds is None
    assert early.eta_low_seconds is None
    assert backward == early
    assert invalid == early
    assert early.progress_percent == 39.0


def test_estimator_expands_eta_after_stall_and_recovers_without_negative_eta() -> None:
    clock = FakeClock()
    estimator = ProgressEstimator(
        clock=clock,
        minimum_observation_seconds=1,
        stall_seconds=4,
    )

    estimator.observe(1, 10)
    clock.advance(2)
    normal = estimator.observe(3, 10)
    clock.advance(5)
    stalled = estimator.current()
    clock.advance(1)
    recovered = estimator.observe(5, 10)

    assert stalled.confidence == "low"
    assert stalled.eta_high_seconds > normal.eta_high_seconds
    assert recovered.eta_low_seconds >= 0
    assert recovered.eta_high_seconds >= recovered.eta_low_seconds
    assert recovered.progress_percent > normal.progress_percent
