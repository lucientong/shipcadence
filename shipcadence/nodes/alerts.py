"""Alert and report formatting nodes.

``format_report`` is the leaf node of the DORA pipeline: it receives
``DORAMetrics`` and produces a display-ready dict.

``check_thresholds`` is an optional node for the alert pipeline that
evaluates DORA metrics against configurable thresholds and flags
degradations.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from dagloom import node

from shipcadence.models import DORAMetrics

# ---------------------------------------------------------------------------
# Alert thresholds
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class AlertThresholds:
    """Configurable alert thresholds for DORA metrics."""

    min_deploys_per_week: float = 1.0
    max_lead_time_hours: float = 168.0  # 1 week
    max_cfr: float = 0.15  # 15 %
    max_mttr_hours: float = 24.0  # 1 day


@dataclass(frozen=True, slots=True)
class AlertResult:
    """Result of threshold evaluation."""

    alerts: tuple[str, ...]
    metrics: DORAMetrics
    degraded: bool  # True if any threshold breached


DEFAULT_THRESHOLDS = AlertThresholds()


def evaluate_thresholds(
    metrics: DORAMetrics,
    thresholds: AlertThresholds = DEFAULT_THRESHOLDS,
) -> AlertResult:
    """Check metrics against thresholds and return alerts."""
    alerts: list[str] = []

    if metrics.deployment_frequency_weekly < thresholds.min_deploys_per_week:
        alerts.append(
            f"Deployment frequency dropped to {metrics.deployment_frequency_weekly:.1f}/week "
            f"(threshold: >={thresholds.min_deploys_per_week:.1f}/week)"
        )

    if metrics.lead_time_median_hours > thresholds.max_lead_time_hours:
        alerts.append(
            f"Lead time is {metrics.lead_time_median_hours:.1f}h "
            f"(threshold: <={thresholds.max_lead_time_hours:.1f}h)"
        )

    if metrics.change_failure_rate > thresholds.max_cfr:
        alerts.append(
            f"Change failure rate is {metrics.change_failure_rate:.1%} "
            f"(threshold: <={thresholds.max_cfr:.1%})"
        )

    if metrics.mttr_median_hours > thresholds.max_mttr_hours:
        alerts.append(
            f"MTTR is {metrics.mttr_median_hours:.1f}h "
            f"(threshold: <={thresholds.max_mttr_hours:.1f}h)"
        )

    return AlertResult(
        alerts=tuple(alerts),
        metrics=metrics,
        degraded=len(alerts) > 0,
    )


@node(name="check_thresholds")
def check_thresholds(metrics: DORAMetrics) -> dict[str, Any]:
    """Evaluate DORA metrics and route to the appropriate severity branch.

    Returns a dict with a ``"branch"`` key that Dagloom uses to select
    which downstream branch node to execute:

    * ``"critical"`` — 3+ thresholds breached
    * ``"warning"``  — 1–2 thresholds breached
    * ``"ok"``       — all metrics healthy

    The ``"data"`` key carries the ``AlertResult`` for downstream nodes.
    """
    result = evaluate_thresholds(metrics)
    n_alerts = len(result.alerts)
    if n_alerts >= 3:
        severity = "critical"
    elif n_alerts >= 1:
        severity = "warning"
    else:
        severity = "ok"
    return {"branch": severity, "data": result}


@node(name="critical")
def handle_critical(payload: dict[str, Any]) -> dict[str, Any]:
    """Handle critical alert — 3+ DORA thresholds breached."""
    result: AlertResult = payload["data"]
    return {
        "severity": "critical",
        "alerts": result.alerts,
        "metrics": result.metrics,
        "message": f"CRITICAL: {len(result.alerts)} DORA thresholds breached",
    }


@node(name="warning")
def handle_warning(payload: dict[str, Any]) -> dict[str, Any]:
    """Handle warning alert — 1–2 DORA thresholds breached."""
    result: AlertResult = payload["data"]
    return {
        "severity": "warning",
        "alerts": result.alerts,
        "metrics": result.metrics,
        "message": f"WARNING: {len(result.alerts)} DORA threshold(s) breached",
    }


@node(name="ok")
def handle_ok(payload: dict[str, Any]) -> dict[str, Any]:
    """Handle healthy state — all metrics within thresholds."""
    result: AlertResult = payload["data"]
    return {
        "severity": "ok",
        "alerts": (),
        "metrics": result.metrics,
        "message": "All DORA metrics within thresholds",
    }


# ---------------------------------------------------------------------------
# Report formatting (leaf node of the main pipeline)
# ---------------------------------------------------------------------------


@node(name="format_report")
def format_report(metrics: DORAMetrics) -> dict[str, Any]:
    """Format DORA metrics into a display-ready structure.

    Returns a dict with ``rows`` (one per metric) and ``summary``
    metadata, suitable for rendering as a Rich table, JSON, or Markdown.
    """
    return {
        "metrics": metrics,
        "rows": [
            {
                "metric": "Deployment Frequency",
                "value": f"{metrics.deployment_frequency_weekly:.1f} / week",
                "rating": metrics.df_rating,
            },
            {
                "metric": "Lead Time for Changes",
                "value": (
                    f"{metrics.lead_time_median_hours:.1f}h (p50), "
                    f"{metrics.lead_time_p95_hours:.1f}h (p95)"
                ),
                "rating": metrics.lt_rating,
            },
            {
                "metric": "Change Failure Rate",
                "value": f"{metrics.change_failure_rate:.1%}",
                "rating": metrics.cfr_rating,
            },
            {
                "metric": "Mean Time to Restore",
                "value": (
                    f"{metrics.mttr_median_hours:.1f}h (p50), {metrics.mttr_p95_hours:.1f}h (p95)"
                ),
                "rating": metrics.mttr_rating,
            },
        ],
        "summary": {
            "period_days": metrics.period_days,
            "total_deploys": metrics.total_deploys,
            "total_prs": metrics.total_prs,
            "total_incidents": metrics.total_incidents,
        },
    }
