"""Tests for pipeline assembly and topology."""

from __future__ import annotations

from datetime import UTC

from shipcadence.pipelines.collect import build_pipeline


def test_pipeline_has_correct_root_nodes() -> None:
    p = build_pipeline()
    roots = set(p.root_nodes())
    assert roots == {"fetch_pulls", "fetch_deployments", "fetch_issues", "pass_config"}


def test_pipeline_has_single_leaf() -> None:
    p = build_pipeline()
    assert p.leaf_nodes() == ["format_report"]


def test_pipeline_transform_all_has_four_predecessors() -> None:
    p = build_pipeline()
    preds = set(p.predecessors("transform_all"))
    assert preds == {"fetch_pulls", "fetch_deployments", "fetch_issues", "pass_config"}


def test_pipeline_linear_tail() -> None:
    p = build_pipeline()
    assert p.successors("transform_all") == ["compute_metrics"]
    assert p.successors("compute_metrics") == ["format_report"]
    assert p.successors("format_report") == []


def test_pipeline_validates() -> None:
    """Pipeline should pass DAG validation (no cycles)."""
    p = build_pipeline()
    p.validate()  # raises CycleError if invalid


def test_pipeline_node_count() -> None:
    p = build_pipeline()
    assert len(p) == 7  # 4 roots + transform + compute + format


def test_pipeline_end_to_end_with_mocked_nodes() -> None:
    """Run the full pipeline with patched fetch nodes."""
    from datetime import datetime, timedelta
    from unittest.mock import AsyncMock

    p = build_pipeline()
    now = datetime.now(UTC)

    raw_pulls = [
        {
            "number": 1,
            "title": "PR",
            "merged_at": (now - timedelta(days=3)).isoformat(),
            "created_at": (now - timedelta(days=5)).isoformat(),
            "updated_at": (now - timedelta(days=3)).isoformat(),
            "merge_commit_sha": "sha1",
            "user": {"login": "dev"},
        }
    ]
    raw_deploys = [
        {
            "id": 100,
            "sha": "sha1",
            "environment": "production",
            "created_at": (now - timedelta(days=3, hours=-1)).isoformat(),
            "status": "success",
            "_source": "deployment_api",
        }
    ]
    raw_issues = [
        {
            "number": 10,
            "title": "Outage",
            "created_at": (now - timedelta(days=3, hours=-2)).isoformat(),
            "closed_at": (now - timedelta(days=3, hours=-5)).isoformat(),
            "labels": [{"name": "incident"}],
            "state": "closed",
        }
    ]

    # Patch the underlying functions on the Node objects.
    p._nodes["fetch_pulls"].fn = AsyncMock(return_value=raw_pulls)
    p._nodes["fetch_deployments"].fn = AsyncMock(return_value=raw_deploys)
    p._nodes["fetch_issues"].fn = AsyncMock(return_value=raw_issues)

    result = p.run(owner="acme", repo="app", token="fake", days=30)

    assert "rows" in result
    assert len(result["rows"]) == 4
    assert result["summary"]["total_deploys"] == 1
    assert result["summary"]["total_prs"] == 1
    assert result["summary"]["total_incidents"] == 1
