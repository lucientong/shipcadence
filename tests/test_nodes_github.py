"""Tests for GitHub collection nodes."""

from __future__ import annotations

import httpx
import pytest
import respx

from shipcadence.nodes.github import fetch_deployments, fetch_issues, fetch_pulls

# ---------------------------------------------------------------------------
# fetch_pulls
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_fetch_pulls_returns_merged_only(sample_raw_pulls: list[dict]) -> None:
    """Only PRs with non-null merged_at should be returned."""
    with respx.mock:
        respx.get(
            "https://api.github.com/repos/acme/app/pulls",
        ).mock(
            side_effect=[
                httpx.Response(200, json=sample_raw_pulls),
                httpx.Response(200, json=[]),
            ]
        )
        result = await fetch_pulls.fn(owner="acme", repo="app", token="fake", days=90)

    # sample_raw_pulls has 3 items, but one has merged_at=None
    assert len(result) == 2
    assert all(pr["merged_at"] is not None for pr in result)


@pytest.mark.asyncio
async def test_fetch_pulls_empty_repo() -> None:
    with respx.mock:
        respx.get(
            "https://api.github.com/repos/acme/empty/pulls",
        ).mock(return_value=httpx.Response(200, json=[]))
        result = await fetch_pulls.fn(owner="acme", repo="empty", token="fake", days=90)

    assert result == []


# ---------------------------------------------------------------------------
# fetch_deployments
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_fetch_deployments_uses_deployments_api(
    sample_raw_deployments: list[dict],
) -> None:
    with respx.mock:
        respx.get(
            "https://api.github.com/repos/acme/app/deployments",
        ).mock(
            side_effect=[
                httpx.Response(200, json=sample_raw_deployments),
                httpx.Response(200, json=[]),
            ]
        )
        result = await fetch_deployments.fn(owner="acme", repo="app", token="fake", days=90)

    assert len(result) == 2
    assert all(d["_source"] == "deployment_api" for d in result)


@pytest.mark.asyncio
async def test_fetch_deployments_falls_back_to_releases(
    sample_raw_releases: list[dict],
) -> None:
    """When deployments API returns empty, fall back to releases."""
    with respx.mock:
        respx.get(
            "https://api.github.com/repos/acme/app/deployments",
        ).mock(return_value=httpx.Response(200, json=[]))
        respx.get(
            "https://api.github.com/repos/acme/app/releases",
        ).mock(
            side_effect=[
                httpx.Response(200, json=sample_raw_releases),
                httpx.Response(200, json=[]),
            ]
        )
        result = await fetch_deployments.fn(owner="acme", repo="app", token="fake", days=90)

    assert len(result) == 1
    assert result[0]["_source"] == "release"


# ---------------------------------------------------------------------------
# fetch_issues
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_fetch_issues_filters_by_label(sample_raw_issues: list[dict]) -> None:
    with respx.mock:
        # Each label query returns our sample (deduplicated by number)
        respx.get(
            "https://api.github.com/repos/acme/app/issues",
        ).mock(
            side_effect=[
                httpx.Response(200, json=sample_raw_issues),
                httpx.Response(200, json=[]),  # end of page for label 1
                httpx.Response(200, json=sample_raw_issues),
                httpx.Response(200, json=[]),  # end of page for label 2
                httpx.Response(200, json=sample_raw_issues),
                httpx.Response(200, json=[]),  # end of page for label 3
                httpx.Response(200, json=sample_raw_issues),
                httpx.Response(200, json=[]),  # end of page for label 4
            ]
        )
        result = await fetch_issues.fn(owner="acme", repo="app", token="fake", days=90)

    # Deduplication by issue number: only 2 unique issues
    assert len(result) == 2
    issue_numbers = {i["number"] for i in result}
    assert issue_numbers == {99, 100}


@pytest.mark.asyncio
async def test_fetch_issues_excludes_pull_requests() -> None:
    """Issues that are actually PRs (have 'pull_request' key) should be excluded."""
    pr_issue = {
        "number": 50,
        "title": "A PR",
        "created_at": "2026-01-01T00:00:00Z",
        "closed_at": None,
        "labels": [{"name": "incident"}],
        "pull_request": {"url": "..."},
    }
    with respx.mock:
        respx.get(
            "https://api.github.com/repos/acme/app/issues",
        ).mock(
            side_effect=[
                httpx.Response(200, json=[pr_issue]),
                httpx.Response(200, json=[]),
                httpx.Response(200, json=[]),
                httpx.Response(200, json=[]),
                httpx.Response(200, json=[]),
                httpx.Response(200, json=[]),
                httpx.Response(200, json=[]),
                httpx.Response(200, json=[]),
            ]
        )
        result = await fetch_issues.fn(owner="acme", repo="app", token="fake", days=90)

    assert result == []
