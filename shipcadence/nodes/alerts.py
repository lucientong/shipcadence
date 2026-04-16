"""Alert and report formatting nodes.

``format_report`` is the leaf node of the DORA pipeline: it receives
``DORAMetrics`` and produces a display-ready dict.
"""

from __future__ import annotations

from typing import Any

from dagloom import node

from shipcadence.models import DORAMetrics


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
