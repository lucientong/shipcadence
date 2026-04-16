"""Shared test fixtures."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from shipcadence.models import Deployment, Incident, NormalizedData, PullRequest

_NOW = datetime.now(UTC)


# ---------------------------------------------------------------------------
# Raw GitHub API fixtures (dicts as returned by httpx)
# ---------------------------------------------------------------------------


@pytest.fixture()
def sample_raw_pulls() -> list[dict]:
    return [
        {
            "number": 42,
            "title": "Add payment service",
            "merged_at": (_NOW - timedelta(days=5)).isoformat(),
            "created_at": (_NOW - timedelta(days=7)).isoformat(),
            "updated_at": (_NOW - timedelta(days=5)).isoformat(),
            "merge_commit_sha": "abc123",
            "user": {"login": "dev1"},
        },
        {
            "number": 43,
            "title": "Fix auth bug",
            "merged_at": (_NOW - timedelta(days=2)).isoformat(),
            "created_at": (_NOW - timedelta(days=3)).isoformat(),
            "updated_at": (_NOW - timedelta(days=2)).isoformat(),
            "merge_commit_sha": "def456",
            "user": {"login": "dev2"},
        },
        {
            "number": 44,
            "title": "Update README",
            "merged_at": None,  # not merged
            "created_at": (_NOW - timedelta(days=1)).isoformat(),
            "updated_at": (_NOW - timedelta(days=1)).isoformat(),
            "merge_commit_sha": None,
            "user": {"login": "dev1"},
            "state": "closed",
        },
    ]


@pytest.fixture()
def sample_raw_deployments() -> list[dict]:
    return [
        {
            "id": 1001,
            "sha": "abc123",
            "environment": "production",
            "created_at": (_NOW - timedelta(days=5, hours=-2)).isoformat(),
            "status": "success",
            "_source": "deployment_api",
        },
        {
            "id": 1002,
            "sha": "def456",
            "environment": "production",
            "created_at": (_NOW - timedelta(days=2, hours=-1)).isoformat(),
            "status": "success",
            "_source": "deployment_api",
        },
    ]


@pytest.fixture()
def sample_raw_releases() -> list[dict]:
    return [
        {
            "id": 2001,
            "tag_name": "v1.0.0",
            "target_commitish": "abc123",
            "published_at": (_NOW - timedelta(days=5)).isoformat(),
            "created_at": (_NOW - timedelta(days=5)).isoformat(),
            "_source": "release",
        },
    ]


@pytest.fixture()
def sample_raw_issues() -> list[dict]:
    return [
        {
            "number": 99,
            "title": "Production outage - payment service",
            "created_at": (_NOW - timedelta(days=5, hours=-3)).isoformat(),
            "closed_at": (_NOW - timedelta(days=5, hours=-6)).isoformat(),
            "labels": [{"name": "incident"}],
            "state": "closed",
        },
        {
            "number": 100,
            "title": "Degraded API latency",
            "created_at": (_NOW - timedelta(days=1)).isoformat(),
            "closed_at": None,
            "labels": [{"name": "incident"}, {"name": "severity/1"}],
            "state": "open",
        },
    ]


# ---------------------------------------------------------------------------
# Typed model fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def sample_pulls() -> tuple[PullRequest, ...]:
    return (
        PullRequest(
            number=42,
            title="Add payment service",
            merged_at=_NOW - timedelta(days=5),
            merge_commit_sha="abc123",
            author="dev1",
            created_at=_NOW - timedelta(days=7),
        ),
        PullRequest(
            number=43,
            title="Fix auth bug",
            merged_at=_NOW - timedelta(days=2),
            merge_commit_sha="def456",
            author="dev2",
            created_at=_NOW - timedelta(days=3),
        ),
    )


@pytest.fixture()
def sample_deployments() -> tuple[Deployment, ...]:
    return (
        Deployment(
            id="1001",
            sha="abc123",
            environment="production",
            created_at=_NOW - timedelta(days=5, hours=-2),
            status="success",
            source="deployment_api",
        ),
        Deployment(
            id="1002",
            sha="def456",
            environment="production",
            created_at=_NOW - timedelta(days=2, hours=-1),
            status="success",
            source="deployment_api",
        ),
    )


@pytest.fixture()
def sample_incidents() -> tuple[Incident, ...]:
    return (
        Incident(
            number=99,
            title="Production outage - payment service",
            created_at=_NOW - timedelta(days=5, hours=-3),
            closed_at=_NOW - timedelta(days=5, hours=-6),
            labels=("incident",),
        ),
        Incident(
            number=100,
            title="Degraded API latency",
            created_at=_NOW - timedelta(days=1),
            closed_at=None,
            labels=("incident", "severity/1"),
        ),
    )


@pytest.fixture()
def sample_normalized_data(
    sample_pulls: tuple[PullRequest, ...],
    sample_deployments: tuple[Deployment, ...],
    sample_incidents: tuple[Incident, ...],
) -> NormalizedData:
    return NormalizedData(
        pulls=sample_pulls,
        deployments=sample_deployments,
        incidents=sample_incidents,
        pr_deploy_map={"abc123": "1001", "def456": "1002"},
        period_days=90,
    )
