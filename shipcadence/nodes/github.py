"""GitHub API data collection nodes.

Each node is an async function decorated with ``@node`` so Dagloom can
orchestrate retries, caching, and timeout.  All three share the same
parameter signature (``owner``, ``repo``, ``token``, ``days``) so they
work as independent root nodes in a fan-out pipeline.

Uses Dagloom's ``HTTPConnector`` with built-in ``paginate()``
(v1.0.3, ``link_header`` strategy) for automatic GitHub pagination.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from dagloom import node
from dagloom.connectors.base import ConnectionConfig
from dagloom.connectors.http import HTTPConnector

GITHUB_API = "https://api.github.com"

# Labels that indicate a production incident.
_DEFAULT_INCIDENT_LABELS = frozenset(
    {
        "incident",
        "outage",
        "severity/1",
        "severity/2",
    }
)


def _github_config(token: str) -> ConnectionConfig:
    """Build a ``ConnectionConfig`` for the GitHub API."""
    return ConnectionConfig(
        host="api.github.com",
        timeout=25.0,
        extra={
            "base_url": GITHUB_API,
            "headers": {
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
            },
        },
    )


def _since_iso(days: int) -> str:
    """Return an ISO-8601 timestamp *days* ago from now (UTC)."""
    return (datetime.now(UTC) - timedelta(days=days)).isoformat()


# ---------------------------------------------------------------------------
# fetch_pulls
# ---------------------------------------------------------------------------


@node(retry=3, cache=True, timeout=30.0)
async def fetch_pulls(owner: str, repo: str, token: str, days: int = 90) -> list[dict[str, Any]]:
    """Fetch merged pull requests within the analysis window.

    Uses ``HTTPConnector.paginate()`` with ``link_header`` strategy
    for automatic GitHub-style pagination.
    """
    since = _since_iso(days)
    pulls: list[dict[str, Any]] = []

    async with HTTPConnector(_github_config(token)) as http:
        async for batch in http.paginate(
            "GET",
            path=f"/repos/{owner}/{repo}/pulls",
            strategy="link_header",
            params={
                "state": "closed",
                "sort": "updated",
                "direction": "desc",
            },
        ):
            for pr in batch:
                merged_at = pr.get("merged_at")
                if merged_at and merged_at >= since:
                    pulls.append(pr)
                elif pr.get("updated_at", "") < since:
                    return pulls

    return pulls


# ---------------------------------------------------------------------------
# fetch_deployments
# ---------------------------------------------------------------------------


@node(retry=3, cache=True, timeout=30.0)
async def fetch_deployments(
    owner: str,
    repo: str,
    token: str,
    days: int = 90,
) -> list[dict[str, Any]]:
    """Fetch production deployment records.

    Tries the GitHub Deployments API first.  If no deployments are found,
    falls back to the Releases API (common for projects that deploy via
    ``git tag`` / GitHub Release).

    Each returned dict is annotated with ``"_source": "deployment_api"``
    or ``"_source": "release"`` so downstream transforms know the shape.
    """
    since = _since_iso(days)

    async with HTTPConnector(_github_config(token)) as http:
        # --- Try Deployments API ---
        deploys = await _fetch_deployments_api(http, owner, repo, since)
        if deploys:
            return deploys

        # --- Fallback: Releases API ---
        return await _fetch_releases_api(http, owner, repo, since)


async def _fetch_deployments_api(
    http: HTTPConnector,
    owner: str,
    repo: str,
    since: str,
) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    async for batch in http.paginate(
        "GET",
        path=f"/repos/{owner}/{repo}/deployments",
        strategy="link_header",
        params={"environment": "production"},
    ):
        for deploy in batch:
            if deploy.get("created_at", "") >= since:
                deploy["_source"] = "deployment_api"
                results.append(deploy)
            else:
                return results

    return results


async def _fetch_releases_api(
    http: HTTPConnector,
    owner: str,
    repo: str,
    since: str,
) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    async for batch in http.paginate(
        "GET",
        path=f"/repos/{owner}/{repo}/releases",
        strategy="link_header",
    ):
        for release in batch:
            published = release.get("published_at") or release.get("created_at", "")
            if published >= since:
                release["_source"] = "release"
                results.append(release)
            else:
                return results

    return results


# ---------------------------------------------------------------------------
# fetch_issues
# ---------------------------------------------------------------------------


@node(retry=3, cache=True, timeout=30.0)
async def fetch_issues(
    owner: str,
    repo: str,
    token: str,
    days: int = 90,
) -> list[dict[str, Any]]:
    """Fetch issues labelled as incidents within the analysis window.

    Queries once per incident label and deduplicates by issue number.
    """
    since = _since_iso(days)
    seen: set[int] = set()
    issues: list[dict[str, Any]] = []

    async with HTTPConnector(_github_config(token)) as http:
        for label in sorted(_DEFAULT_INCIDENT_LABELS):
            async for batch in http.paginate(
                "GET",
                path=f"/repos/{owner}/{repo}/issues",
                strategy="link_header",
                params={
                    "labels": label,
                    "state": "all",
                    "since": since,
                    "sort": "created",
                    "direction": "desc",
                },
            ):
                for issue in batch:
                    num = issue["number"]
                    if num not in seen and not issue.get("pull_request"):
                        seen.add(num)
                        issues.append(issue)

    return issues
