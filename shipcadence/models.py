"""Data models for ShipCadence DORA metrics."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

# ---------------------------------------------------------------------------
# Raw-data models (output of transform nodes)
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class PullRequest:
    """A merged pull request."""

    number: int
    title: str
    merged_at: datetime
    merge_commit_sha: str
    author: str
    created_at: datetime


@dataclass(frozen=True, slots=True)
class Deployment:
    """A production deployment record."""

    id: str
    sha: str
    environment: str
    created_at: datetime
    status: str  # "success" | "failure"
    source: str  # "deployment_api" | "release" | "tag"


@dataclass(frozen=True, slots=True)
class Incident:
    """A production incident (derived from GitHub issues)."""

    number: int
    title: str
    created_at: datetime
    closed_at: datetime | None
    labels: tuple[str, ...]


# ---------------------------------------------------------------------------
# Intermediate pipeline data
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class NormalizedData:
    """Cleaned and correlated data flowing through the pipeline."""

    pulls: tuple[PullRequest, ...]
    deployments: tuple[Deployment, ...]
    incidents: tuple[Incident, ...]
    pr_deploy_map: dict[str, str]  # merge_commit_sha -> deployment id
    period_days: int


# ---------------------------------------------------------------------------
# DORA metrics output
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class DORAMetrics:
    """Computed DORA metrics with benchmark ratings."""

    # Deployment Frequency
    deployment_frequency: float  # deploys per day
    deployment_frequency_weekly: float  # deploys per week

    # Lead Time for Changes
    lead_time_median_hours: float
    lead_time_p95_hours: float

    # Change Failure Rate
    change_failure_rate: float  # 0.0 – 1.0

    # Mean Time to Restore
    mttr_median_hours: float
    mttr_p95_hours: float

    # Metadata
    period_days: int
    total_deploys: int
    total_prs: int
    total_incidents: int

    # DORA benchmark ratings
    df_rating: str  # "Elite" | "High" | "Medium" | "Low"
    lt_rating: str
    cfr_rating: str
    mttr_rating: str
