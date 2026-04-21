#!/usr/bin/env python3
"""Example: Programmatic usage of ShipCadence pipelines.

Run with:
    GITHUB_TOKEN=ghp_xxx python examples/analyze_repo.py
"""

from __future__ import annotations

import os
import sys

# ---------------------------------------------------------------------------
# 1. Basic analysis via the high-level API
# ---------------------------------------------------------------------------


def basic_analysis() -> None:
    """Run a DORA analysis and print the report."""
    from shipcadence.pipelines.collect import run_analysis
    from shipcadence.report import to_json, to_markdown

    token = os.environ.get("GITHUB_TOKEN", "")
    if not token:
        print("Set GITHUB_TOKEN to run this example.")
        sys.exit(1)

    report = run_analysis(owner="lucientong", repo="dagloom", token=token, days=90)

    # Access structured metrics.
    metrics = report["metrics"]
    print(f"Deployment Frequency: {metrics.deployment_frequency_weekly:.1f}/week")
    print(f"Lead Time (p50):      {metrics.lead_time_median_hours:.1f}h")
    print(f"Change Failure Rate:  {metrics.change_failure_rate:.1%}")
    print(f"MTTR (p50):           {metrics.mttr_median_hours:.1f}h")
    print()

    # Export as JSON.
    print(to_json(metrics))
    print()

    # Export as Markdown.
    print(to_markdown(report))


# ---------------------------------------------------------------------------
# 2. Custom thresholds for alert evaluation
# ---------------------------------------------------------------------------


def custom_alerts() -> None:
    """Evaluate metrics against custom thresholds."""
    from shipcadence.nodes.alerts import AlertThresholds, evaluate_thresholds
    from shipcadence.pipelines.collect import run_analysis

    token = os.environ.get("GITHUB_TOKEN", "")
    if not token:
        print("Set GITHUB_TOKEN to run this example.")
        sys.exit(1)

    report = run_analysis(owner="lucientong", repo="dagloom", token=token, days=30)
    metrics = report["metrics"]

    # Strict thresholds for a high-performing team.
    thresholds = AlertThresholds(
        min_deploys_per_week=3.0,
        max_lead_time_hours=48.0,
        max_cfr=0.05,
        max_mttr_hours=4.0,
    )

    result = evaluate_thresholds(metrics, thresholds)
    if result.degraded:
        print("ALERTS:")
        for alert in result.alerts:
            print(f"  - {alert}")
    else:
        print("All metrics within thresholds.")


# ---------------------------------------------------------------------------
# 3. Inspect the pipeline DAG
# ---------------------------------------------------------------------------


def inspect_pipeline() -> None:
    """Build and visualize the pipeline topology."""
    from shipcadence.pipelines.collect import build_pipeline

    pipeline = build_pipeline()
    print(pipeline.visualize())
    print()
    print(f"Root nodes:  {pipeline.root_nodes()}")
    print(f"Leaf nodes:  {pipeline.leaf_nodes()}")
    print(f"Total nodes: {len(pipeline)}")


if __name__ == "__main__":
    print("=== Pipeline Topology ===")
    inspect_pipeline()
    print()

    if os.environ.get("GITHUB_TOKEN"):
        print("=== Basic Analysis ===")
        basic_analysis()
        print()
        print("=== Custom Alerts ===")
        custom_alerts()
    else:
        print("Set GITHUB_TOKEN to run the analysis examples.")
