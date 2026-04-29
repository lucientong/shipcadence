"""Tests for the alert pipeline and branch routing."""

from __future__ import annotations

from shipcadence.pipelines.alert import build_alert_pipeline


def test_alert_pipeline_topology() -> None:
    p = build_alert_pipeline()
    roots = set(p.root_nodes())
    assert roots == {"fetch_pulls", "fetch_deployments", "fetch_issues", "pass_config"}
    # Leaf nodes are the 3 branch targets
    leaves = set(p.leaf_nodes())
    assert leaves == {"critical", "warning", "ok"}


def test_alert_pipeline_has_branch_after_check_thresholds() -> None:
    p = build_alert_pipeline()
    successors = set(p.successors("check_thresholds"))
    assert successors == {"critical", "warning", "ok"}


def test_alert_pipeline_with_webhook() -> None:
    p = build_alert_pipeline(webhook_url="https://hooks.example.com/alert")
    assert p.notify_on is not None
    assert "success" in p.notify_on
    assert "failure" in p.notify_on


def test_alert_pipeline_without_webhook() -> None:
    p = build_alert_pipeline()
    assert p.notify_on is None


def test_alert_pipeline_validates() -> None:
    p = build_alert_pipeline()
    p.validate()


def test_alert_pipeline_node_count() -> None:
    p = build_alert_pipeline()
    # 4 roots + transform + compute + check_thresholds + 3 branches = 10
    assert len(p) == 10
