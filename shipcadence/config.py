"""Configuration management for ShipCadence."""

from __future__ import annotations

from dataclasses import dataclass

DEFAULT_INCIDENT_LABELS: tuple[str, ...] = (
    "incident",
    "outage",
    "severity/1",
    "severity/2",
)


@dataclass(frozen=True, slots=True)
class RepoConfig:
    """Configuration for analysing a single repository."""

    owner: str
    repo: str
    token: str
    days: int = 90
    incident_labels: tuple[str, ...] = DEFAULT_INCIDENT_LABELS

    @classmethod
    def from_slug(cls, slug: str, token: str, *, days: int = 90) -> RepoConfig:
        """Create from ``owner/repo`` slug.

        Raises:
            ValueError: If *slug* is not in ``owner/repo`` format.
        """
        parts = slug.split("/", 1)
        if len(parts) != 2 or not all(parts):
            raise ValueError(f"Repository must be in 'owner/repo' format, got {slug!r}")
        return cls(owner=parts[0], repo=parts[1], token=token, days=days)
