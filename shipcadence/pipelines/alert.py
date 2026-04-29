"""Alert pipeline — checks DORA metrics and routes by severity.

Uses Dagloom's ``Branch`` (``|`` operator) for conditional routing
after threshold evaluation.

Topology::

    [fetch nodes] >> transform_all >> compute_metrics >> check_thresholds
                                                             │
                                                    ┌────────┼────────┐
                                                 critical  warning    ok

``check_thresholds`` returns ``{"branch": "critical"|"warning"|"ok"}``.
Dagloom selects the matching branch node; others are SKIPPED.
"""

from __future__ import annotations

from dagloom import parallel

from shipcadence.nodes.alerts import check_thresholds, handle_critical, handle_ok, handle_warning
from shipcadence.nodes.github import fetch_deployments, fetch_issues, fetch_pulls
from shipcadence.nodes.metrics import compute_metrics
from shipcadence.nodes.transforms import pass_config, transform_all


def build_alert_pipeline(
    webhook_url: str | None = None,
):  # noqa: ANN201
    """Construct a pipeline that computes metrics and routes alerts by severity.

    If *webhook_url* is provided, the pipeline's ``notify_on`` is
    configured to POST results to the webhook on both success and failure.
    """
    pipeline = (
        parallel(fetch_pulls, fetch_deployments, fetch_issues, pass_config)
        >> transform_all
        >> compute_metrics
        >> check_thresholds
        >> (handle_critical | handle_warning | handle_ok)
    )

    if webhook_url:
        pipeline.notify_on = {
            "success": [f"webhook://{webhook_url}"],
            "failure": [f"webhook://{webhook_url}"],
        }

    return pipeline
