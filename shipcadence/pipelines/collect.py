"""Pipeline assembly for ShipCadence DORA metrics.

Uses Dagloom's ``parallel()`` helper (v1.0.1) to express the fan-out /
fan-in topology declaratively::

    parallel(fetch_pulls, fetch_deployments, fetch_issues, pass_config)
        >> transform_all >> compute_metrics >> format_report

All four root nodes receive filtered ``**inputs`` (each only gets the
kwargs matching its signature).  ``transform_all`` has four predecessors
and receives a dict of their outputs.
"""

from __future__ import annotations

from typing import Any

from dagloom import parallel

from shipcadence.nodes.alerts import format_report
from shipcadence.nodes.github import fetch_deployments, fetch_issues, fetch_pulls
from shipcadence.nodes.metrics import compute_metrics
from shipcadence.nodes.transforms import pass_config, transform_all


def build_pipeline():  # noqa: ANN201
    """Construct the DORA metrics pipeline.

    Topology::

        fetch_pulls ────────┐
        fetch_deployments ──┤
        fetch_issues ───────┤──► transform_all ──► compute_metrics ──► format_report
        pass_config ────────┘
    """
    return (
        parallel(fetch_pulls, fetch_deployments, fetch_issues, pass_config)
        >> transform_all
        >> compute_metrics
        >> format_report
    )


def run_analysis(
    owner: str,
    repo: str,
    token: str,
    days: int = 90,
) -> dict[str, Any]:
    """Execute the DORA pipeline synchronously.

    Returns the display-ready report dict from ``format_report``.
    """
    pipeline = build_pipeline()
    return pipeline.run(owner=owner, repo=repo, token=token, days=days)  # type: ignore[return-value]


async def arun_analysis(
    owner: str,
    repo: str,
    token: str,
    days: int = 90,
) -> dict[str, Any]:
    """Execute the DORA pipeline asynchronously (concurrent fetches)."""
    pipeline = build_pipeline()
    return await pipeline.arun(owner=owner, repo=repo, token=token, days=days)  # type: ignore[return-value]
