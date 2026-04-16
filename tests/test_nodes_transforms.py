"""Tests for data transformation and normalisation."""

from __future__ import annotations

from datetime import UTC

from shipcadence.nodes.transforms import (
    correlate_pr_deploy,
    normalize_deployments,
    normalize_issues,
    normalize_pulls,
    pass_config,
    transform_all,
)

# ---------------------------------------------------------------------------
# normalize_pulls
# ---------------------------------------------------------------------------


def test_normalize_pulls_filters_unmerged(sample_raw_pulls: list[dict]) -> None:
    result = normalize_pulls(sample_raw_pulls)
    # One of three sample PRs has merged_at=None → filtered out
    assert len(result) == 2
    assert result[0].number == 42
    assert result[0].merge_commit_sha == "abc123"
    assert result[0].merged_at.tzinfo is not None


def test_normalize_pulls_empty() -> None:
    assert normalize_pulls([]) == []


# ---------------------------------------------------------------------------
# normalize_deployments
# ---------------------------------------------------------------------------


def test_normalize_deployments_api_source(sample_raw_deployments: list[dict]) -> None:
    result = normalize_deployments(sample_raw_deployments)
    assert len(result) == 2
    assert result[0].source == "deployment_api"
    assert result[0].sha == "abc123"


def test_normalize_deployments_release_source(sample_raw_releases: list[dict]) -> None:
    result = normalize_deployments(sample_raw_releases)
    assert len(result) == 1
    assert result[0].source == "release"
    assert result[0].sha == "abc123"  # target_commitish


# ---------------------------------------------------------------------------
# normalize_issues
# ---------------------------------------------------------------------------


def test_normalize_issues(sample_raw_issues: list[dict]) -> None:
    result = normalize_issues(sample_raw_issues)
    assert len(result) == 2
    assert result[0].number == 99
    assert result[0].closed_at is not None
    assert result[1].closed_at is None  # open incident
    assert "incident" in result[0].labels


# ---------------------------------------------------------------------------
# correlate_pr_deploy
# ---------------------------------------------------------------------------


def test_correlate_exact_sha_match(sample_pulls, sample_deployments) -> None:
    mapping = correlate_pr_deploy(list(sample_pulls), list(sample_deployments))
    # Both PRs have exact SHA matches
    assert mapping["abc123"] == "1001"
    assert mapping["def456"] == "1002"


def test_correlate_no_match() -> None:
    from datetime import datetime, timedelta

    from shipcadence.models import Deployment, PullRequest

    now = datetime.now(UTC)
    pr = PullRequest(
        number=1,
        title="x",
        merged_at=now,
        merge_commit_sha="unmatched_sha",
        author="a",
        created_at=now - timedelta(days=1),
    )
    dep = Deployment(
        id="d1",
        sha="other_sha",
        environment="production",
        created_at=now - timedelta(days=30),  # way before PR
        status="success",
        source="deployment_api",
    )
    mapping = correlate_pr_deploy([pr], [dep])
    assert mapping == {}  # no match: deploy is before PR and SHA doesn't match


# ---------------------------------------------------------------------------
# pass_config
# ---------------------------------------------------------------------------


def test_pass_config() -> None:
    result = pass_config(days=30)
    assert result == {"days": 30}


# ---------------------------------------------------------------------------
# transform_all (integration)
# ---------------------------------------------------------------------------


def test_transform_all_receives_predecessor_dict(
    sample_raw_pulls: list[dict],
    sample_raw_deployments: list[dict],
    sample_raw_issues: list[dict],
) -> None:
    """Simulate the dict Dagloom passes from multiple predecessors."""
    raw_data = {
        "fetch_pulls": sample_raw_pulls,
        "fetch_deployments": sample_raw_deployments,
        "fetch_issues": sample_raw_issues,
        "pass_config": {"days": 30},
    }
    result = transform_all(raw_data)

    assert len(result.pulls) == 2  # one unmerged filtered out
    assert len(result.deployments) == 2
    assert len(result.incidents) == 2
    assert result.period_days == 30
    assert isinstance(result.pr_deploy_map, dict)


def test_transform_all_empty_data() -> None:
    raw_data = {
        "fetch_pulls": [],
        "fetch_deployments": [],
        "fetch_issues": [],
        "pass_config": {"days": 90},
    }
    result = transform_all(raw_data)
    assert len(result.pulls) == 0
    assert len(result.deployments) == 0
    assert result.period_days == 90
