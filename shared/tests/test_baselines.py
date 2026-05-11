"""Tests for baseline computation and health scoring."""

from kinship_shared.baselines import (
    compute_deviation,
    compute_health_score,
    classify_trend,
)


def test_compute_deviation_normal():
    """Value at baseline should return ~0."""
    assert abs(compute_deviation(20.0, 20.0, 2.0)) < 0.01


def test_compute_deviation_extreme():
    """Value 3 sigma above should return ~3."""
    d = compute_deviation(26.0, 20.0, 2.0)
    assert abs(d - 3.0) < 0.01


def test_compute_deviation_zero_std():
    """Should handle zero std gracefully without division error."""
    d = compute_deviation(25.0, 20.0, 0.0)
    assert -3.0 <= d <= 3.0


def test_compute_health_score_all_normal():
    """Deviations near 0 should produce score near 100."""
    score = compute_health_score([0.0, 0.0, 0.0])
    assert score > 90


def test_compute_health_score_all_extreme():
    """Large deviations should produce score near 0."""
    score = compute_health_score([3.0, 3.0, 3.0])
    assert score < 30


def test_compute_health_score_empty():
    """No deviations should return neutral 50."""
    assert compute_health_score([]) == 50.0


def test_classify_trend_improving():
    """Rising health scores should classify as improving."""
    assert classify_trend([40.0, 50.0, 60.0]) == "improving"


def test_classify_trend_declining():
    """Falling health scores should classify as declining."""
    assert classify_trend([60.0, 50.0, 40.0]) == "declining"


def test_classify_trend_critical():
    """Very low recent score should classify as critical."""
    assert classify_trend([30.0, 20.0, 10.0]) == "critical"


def test_classify_trend_stable():
    """Flat scores should classify as stable."""
    assert classify_trend([50.0, 51.0, 50.0]) == "stable"


def test_classify_trend_too_few():
    """Fewer than 3 scores should default to stable."""
    assert classify_trend([50.0]) == "stable"
