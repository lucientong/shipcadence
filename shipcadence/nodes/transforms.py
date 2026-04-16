"""Data cleaning, normalisation, and PR-deploy correlation.

The ``transform_all`` node sits at the fan-in point of the pipeline:
it receives a dict of outputs from the three fetch nodes and produces
a single ``NormalizedData`` object for downstream computation.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from dagloom import node

from shipcadence.models import Deployment, Incident, NormalizedData, PullRequest


def _parse_iso(value: str | None) -> datetime | None:
    """Parse a GitHub ISO-8601 timestamp into an aware datetime."""
    if not value:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _parse_iso_required(value: str) -> datetime:
    dt = _parse_iso(value)
    if dt is None:
        raise ValueError(f"Expected ISO-8601 datetime, got {value!r}")
    return dt


# ---------------------------------------------------------------------------
# Normalisation helpers (pure functions, easily testable)
# ---------------------------------------------------------------------------


def normalize_pulls(raw: list[dict[str, Any]]) -> list[PullRequest]:
    """Convert raw GitHub PR dicts to ``PullRequest`` models."""
    results: list[PullRequest] = []
    for pr in raw:
        merged_at = _parse_iso(pr.get("merged_at"))
        if merged_at is None:
            continue  # skip unmerged PRs that slipped through
        results.append(
            PullRequest(
                number=pr["number"],
                title=pr.get("title", ""),
                merged_at=merged_at,
                merge_commit_sha=pr.get("merge_commit_sha", ""),
                author=pr.get("user", {}).get("login", "unknown"),
                created_at=_parse_iso_required(pr["created_at"]),
            )
        )
    return results


def normalize_deployments(raw: list[dict[str, Any]]) -> list[Deployment]:
    """Convert raw GitHub deployment/release dicts to ``Deployment`` models.

    Handles both Deployments API and Releases API shapes (distinguished
    by the ``_source`` annotation added during fetch).
    """
    results: list[Deployment] = []
    for item in raw:
        source = item.get("_source", "deployment_api")
        if source == "release":
            results.append(
                Deployment(
                    id=str(item["id"]),
                    sha=item.get("target_commitish", item.get("tag_name", "")),
                    environment="production",
                    created_at=_parse_iso_required(item.get("published_at") or item["created_at"]),
                    status="success",
                    source="release",
                )
            )
        else:
            results.append(
                Deployment(
                    id=str(item["id"]),
                    sha=item.get("sha", ""),
                    environment=item.get("environment", "production"),
                    created_at=_parse_iso_required(item["created_at"]),
                    status=item.get("status", "success"),
                    source="deployment_api",
                )
            )
    return results


def normalize_issues(raw: list[dict[str, Any]]) -> list[Incident]:
    """Convert raw GitHub issue dicts to ``Incident`` models."""
    results: list[Incident] = []
    for issue in raw:
        labels = tuple(
            lbl["name"] if isinstance(lbl, dict) else str(lbl) for lbl in issue.get("labels", [])
        )
        results.append(
            Incident(
                number=issue["number"],
                title=issue.get("title", ""),
                created_at=_parse_iso_required(issue["created_at"]),
                closed_at=_parse_iso(issue.get("closed_at")),
                labels=labels,
            )
        )
    return results


def correlate_pr_deploy(
    pulls: list[PullRequest],
    deployments: list[Deployment],
) -> dict[str, str]:
    """Match pull requests to deployments.

    Strategy:
    1. **Exact SHA match** — PR ``merge_commit_sha`` equals deployment ``sha``.
    2. **Nearest-future deployment** — for unmatched PRs, pick the first
       deployment whose ``created_at`` is after the PR ``merged_at``
       (within 7 days).

    Returns a mapping ``{merge_commit_sha: deployment_id}``.
    """
    mapping: dict[str, str] = {}
    sha_to_deploy: dict[str, Deployment] = {}
    for dep in deployments:
        if dep.sha:
            sha_to_deploy[dep.sha] = dep

    # Sort deployments by time for fallback matching.
    sorted_deploys = sorted(deployments, key=lambda d: d.created_at)

    for pr in pulls:
        sha = pr.merge_commit_sha

        # Rule 1: exact SHA match
        if sha and sha in sha_to_deploy:
            mapping[sha] = sha_to_deploy[sha].id
            continue

        # Rule 2: nearest future deployment within 7 days
        if not sha:
            continue
        best: Deployment | None = None
        for dep in sorted_deploys:
            if dep.created_at >= pr.merged_at:
                if dep.created_at - pr.merged_at <= timedelta(days=7):
                    best = dep
                break  # first future deploy is closest
        if best is not None:
            mapping[sha] = best.id

    return mapping


# ---------------------------------------------------------------------------
# Pipeline node
# ---------------------------------------------------------------------------


@node(name="pass_config")
def pass_config(days: int = 90) -> dict[str, Any]:
    """Trivial root node that forwards the ``days`` config value.

    This exists because non-root nodes receive predecessor outputs
    (not the original ``**inputs``).  By making ``days`` the output
    of a root node, ``transform_all`` can access it via the merged
    predecessor dict.

    As of Dagloom v1.0.1, root node inputs are filtered by parameter
    signature so this node only receives ``days`` (not owner/repo/token).
    """
    return {"days": days}


@node(name="transform_all")
def transform_all(raw_data: dict[str, Any]) -> NormalizedData:
    """Fan-in transform: receives outputs from all fetch + config nodes.

    Dagloom passes a dict keyed by predecessor node name when a node has
    multiple predecessors::

        {
            "fetch_pulls": [...],
            "fetch_deployments": [...],
            "fetch_issues": [...],
            "pass_config": {"days": 90},
        }
    """
    raw_pulls: list[dict[str, Any]] = raw_data.get("fetch_pulls", [])
    raw_deploys: list[dict[str, Any]] = raw_data.get("fetch_deployments", [])
    raw_issues: list[dict[str, Any]] = raw_data.get("fetch_issues", [])
    config: dict[str, Any] = raw_data.get("pass_config", {})
    days: int = config.get("days", 90) if isinstance(config, dict) else 90

    pulls = normalize_pulls(raw_pulls)
    deployments = normalize_deployments(raw_deploys)
    incidents = normalize_issues(raw_issues)
    pr_deploy_map = correlate_pr_deploy(pulls, deployments)

    return NormalizedData(
        pulls=tuple(pulls),
        deployments=tuple(deployments),
        incidents=tuple(incidents),
        pr_deploy_map=pr_deploy_map,
        period_days=days,
    )
