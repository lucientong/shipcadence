"""Alert pipeline — checks DORA metrics against thresholds.

Extends the main collection pipeline with a ``check_thresholds`` node
and optional webhook notifications via Dagloom's ``Pipeline.notify_on``.

Topology::

    [main pipeline] >> compute_metrics >> check_thresholds
                                             │
                                     (notify_on: webhook)
"""

from __future__ import annotations

from dagloom import parallel

from shipcadence.nodes.alerts import check_thresholds
from shipcadence.nodes.github import fetch_deployments, fetch_issues, fetch_pulls
from shipcadence.nodes.metrics import compute_metrics
from shipcadence.nodes.transforms import pass_config, transform_all


def build_alert_pipeline(
    webhook_url: str | None = None,
):  # noqa: ANN201
    """Construct a pipeline that computes metrics and checks thresholds.

    If *webhook_url* is provided, the pipeline's ``notify_on`` is
    configured to POST results to the webhook on both success and failure.
    """
    pipeline = (
        parallel(fetch_pulls, fetch_deployments, fetch_issues, pass_config)
        >> transform_all
        >> compute_metrics
        >> check_thresholds
    )

    if webhook_url:
        pipeline.notify_on = {
            "success": [f"webhook://{webhook_url}"],
            "failure": [f"webhook://{webhook_url}"],
        }

    return pipeline
