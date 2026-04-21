"""Tests for alert nodes and threshold evaluation."""

from __future__ import annotations

from shipcadence.models import DORAMetrics
from shipcadence.nodes.alerts import (
    AlertThresholds,
    evaluate_thresholds,
)


def _make_metrics(**overrides: object) -> DORAMetrics:
    defaults = {
        "deployment_frequency": 1.0,
        "deployment_frequency_weekly": 7.0,
        "lead_time_median_hours": 12.0,
        "lead_time_p95_hours": 48.0,
        "change_failure_rate": 0.05,
        "mttr_median_hours": 2.0,
        "mttr_p95_hours": 8.0,
        "period_days": 90,
        "total_deploys": 90,
        "total_prs": 120,
        "total_incidents": 5,
        "df_rating": "Elite",
        "lt_rating": "Elite",
        "cfr_rating": "Elite",
        "mttr_rating": "High",
    }
    defaults.update(overrides)
    return DORAMetrics(**defaults)  # type: ignore[arg-type]


def test_no_alerts_when_healthy() -> None:
    result = evaluate_thresholds(_make_metrics())
    assert result.degraded is False
    assert result.alerts == ()


def test_alert_on_low_deployment_frequency() -> None:
    result = evaluate_thresholds(
        _make_metrics(deployment_frequency_weekly=0.5),
        AlertThresholds(min_deploys_per_week=1.0),
    )
    assert result.degraded is True
    assert any("Deployment frequency" in a for a in result.alerts)


def test_alert_on_high_lead_time() -> None:
    result = evaluate_thresholds(
        _make_metrics(lead_time_median_hours=200.0),
        AlertThresholds(max_lead_time_hours=168.0),
    )
    assert result.degraded is True
    assert any("Lead time" in a for a in result.alerts)


def test_alert_on_high_cfr() -> None:
    result = evaluate_thresholds(
        _make_metrics(change_failure_rate=0.25),
        AlertThresholds(max_cfr=0.15),
    )
    assert result.degraded is True
    assert any("failure rate" in a for a in result.alerts)


def test_alert_on_high_mttr() -> None:
    result = evaluate_thresholds(
        _make_metrics(mttr_median_hours=48.0),
        AlertThresholds(max_mttr_hours=24.0),
    )
    assert result.degraded is True
    assert any("MTTR" in a for a in result.alerts)


def test_multiple_alerts() -> None:
    result = evaluate_thresholds(
        _make_metrics(
            deployment_frequency_weekly=0.1,
            lead_time_median_hours=999.0,
            change_failure_rate=0.5,
            mttr_median_hours=200.0,
        ),
    )
    assert result.degraded is True
    assert len(result.alerts) == 4
