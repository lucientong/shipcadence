"""DORA metrics computation nodes.

Receives ``NormalizedData`` from the transform step and produces
``DORAMetrics`` with benchmark ratings.
"""

from __future__ import annotations

import statistics
from datetime import timedelta

from dagloom import node

from shipcadence.models import Deployment, DORAMetrics, Incident, NormalizedData


def _percentile(data: list[float], pct: float) -> float:
    """Compute the *pct*-th percentile of *data* (linear interpolation)."""
    if not data:
        return 0.0
    sorted_data = sorted(data)
    n = len(sorted_data)
    k = (pct / 100) * (n - 1)
    lo = int(k)
    hi = min(lo + 1, n - 1)
    weight = k - lo
    return sorted_data[lo] + weight * (sorted_data[hi] - sorted_data[lo])


# ---------------------------------------------------------------------------
# Individual metric computations
# ---------------------------------------------------------------------------


def deployment_frequency(
    deployments: tuple[Deployment, ...],
    period_days: int,
) -> tuple[float, float]:
    """Return (deploys_per_day, deploys_per_week)."""
    if not deployments or period_days <= 0:
        return 0.0, 0.0
    per_day = len(deployments) / period_days
    return per_day, per_day * 7


def lead_time(
    data: NormalizedData,
) -> tuple[float, float]:
    """Median and p95 hours from PR merge to matched deployment."""
    deploy_by_id: dict[str, Deployment] = {d.id: d for d in data.deployments}
    hours: list[float] = []

    for pr in data.pulls:
        deploy_id = data.pr_deploy_map.get(pr.merge_commit_sha)
        if deploy_id and deploy_id in deploy_by_id:
            delta = (deploy_by_id[deploy_id].created_at - pr.merged_at).total_seconds() / 3600
            if delta >= 0:
                hours.append(delta)

    if not hours:
        return 0.0, 0.0
    return statistics.median(hours), _percentile(hours, 95)


def change_failure_rate(
    deployments: tuple[Deployment, ...],
    incidents: tuple[Incident, ...],
) -> float:
    """Percentage of deployments that caused an incident.

    Heuristic: an incident is attributed to a deployment if the incident
    was created within 24 hours **after** the deployment.
    """
    if not deployments:
        return 0.0

    failure_window = timedelta(hours=24)
    failed_deploy_ids: set[str] = set()

    for inc in incidents:
        for dep in deployments:
            if dep.created_at <= inc.created_at <= dep.created_at + failure_window:
                failed_deploy_ids.add(dep.id)
                break  # one incident → one deployment

    return len(failed_deploy_ids) / len(deployments)


def mttr(incidents: tuple[Incident, ...]) -> tuple[float, float]:
    """Median and p95 hours to restore from incidents (created → closed)."""
    restore_hours: list[float] = []
    for inc in incidents:
        if inc.closed_at is not None:
            hours = (inc.closed_at - inc.created_at).total_seconds() / 3600
            if hours >= 0:
                restore_hours.append(hours)

    if not restore_hours:
        return 0.0, 0.0
    return statistics.median(restore_hours), _percentile(restore_hours, 95)


# ---------------------------------------------------------------------------
# DORA benchmark ratings
# ---------------------------------------------------------------------------


def rate_df(per_day: float) -> str:
    """Rate deployment frequency against DORA benchmarks."""
    if per_day >= 1.0:
        return "Elite"  # on-demand / multiple per day
    if per_day >= 1 / 7:
        return "High"  # weekly to daily
    if per_day >= 1 / 30:
        return "Medium"  # monthly to weekly
    return "Low"


def rate_lt(median_hours: float) -> str:
    """Rate lead time for changes."""
    if median_hours <= 24:
        return "Elite"  # less than one day
    if median_hours <= 168:
        return "High"  # less than one week
    if median_hours <= 720:
        return "Medium"  # less than one month
    return "Low"


def rate_cfr(rate: float) -> str:
    """Rate change failure rate."""
    if rate <= 0.05:
        return "Elite"
    if rate <= 0.10:
        return "High"
    if rate <= 0.15:
        return "Medium"
    return "Low"


def rate_mttr(median_hours: float) -> str:
    """Rate mean time to restore."""
    if median_hours <= 1:
        return "Elite"  # less than one hour
    if median_hours <= 24:
        return "High"  # less than one day
    if median_hours <= 168:
        return "Medium"  # less than one week
    return "Low"


# ---------------------------------------------------------------------------
# Pipeline node
# ---------------------------------------------------------------------------


@node(name="compute_metrics")
def compute_metrics(data: NormalizedData) -> DORAMetrics:
    """Compute all four DORA metrics from normalised data.

    Receives ``NormalizedData`` as a single positional argument (one
    predecessor: ``transform_all``).
    """
    df_day, df_week = deployment_frequency(data.deployments, data.period_days)
    lt_med, lt_p95 = lead_time(data)
    cfr = change_failure_rate(data.deployments, data.incidents)
    mttr_med, mttr_p95 = mttr(data.incidents)

    return DORAMetrics(
        deployment_frequency=df_day,
        deployment_frequency_weekly=df_week,
        lead_time_median_hours=lt_med,
        lead_time_p95_hours=lt_p95,
        change_failure_rate=cfr,
        mttr_median_hours=mttr_med,
        mttr_p95_hours=mttr_p95,
        period_days=data.period_days,
        total_deploys=len(data.deployments),
        total_prs=len(data.pulls),
        total_incidents=len(data.incidents),
        df_rating=rate_df(df_day),
        lt_rating=rate_lt(lt_med),
        cfr_rating=rate_cfr(cfr),
        mttr_rating=rate_mttr(mttr_med),
    )
