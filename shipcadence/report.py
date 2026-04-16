"""Report export helpers (JSON, Markdown)."""

from __future__ import annotations

import json
from dataclasses import asdict
from typing import Any

from shipcadence.models import DORAMetrics


def to_json(metrics: DORAMetrics) -> str:
    """Serialise ``DORAMetrics`` to a pretty-printed JSON string."""
    return json.dumps(asdict(metrics), indent=2, default=str)


def to_markdown(report: dict[str, Any]) -> str:
    """Render a report dict (from ``format_report``) as Markdown."""
    lines = [
        "# DORA Metrics Report",
        "",
        "| Metric | Value | Rating |",
        "|--------|-------|--------|",
    ]
    for row in report["rows"]:
        lines.append(f"| {row['metric']} | {row['value']} | {row['rating']} |")

    s = report["summary"]
    lines.extend(
        [
            "",
            f"**Period:** {s['period_days']} days | "
            f"**Deploys:** {s['total_deploys']} | "
            f"**PRs:** {s['total_prs']} | "
            f"**Incidents:** {s['total_incidents']}",
        ]
    )
    return "\n".join(lines)
