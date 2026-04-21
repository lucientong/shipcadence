"""Tests for the alert pipeline and watch command."""

from __future__ import annotations

from shipcadence.pipelines.alert import build_alert_pipeline


def test_alert_pipeline_topology() -> None:
    p = build_alert_pipeline()
    roots = set(p.root_nodes())
    assert roots == {"fetch_pulls", "fetch_deployments", "fetch_issues", "pass_config"}
    assert p.leaf_nodes() == ["check_thresholds"]
    assert p.successors("compute_metrics") == ["check_thresholds"]


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
