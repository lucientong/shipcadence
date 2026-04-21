# ShipCadence

Lightweight DORA metrics from GitHub, powered by [Dagloom](https://github.com/lucientong/dagloom).

[![CI](https://github.com/lucientong/shipcadence/actions/workflows/ci.yml/badge.svg)](https://github.com/lucientong/shipcadence/actions/workflows/ci.yml)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/license-Apache%202.0-green.svg)](LICENSE)

```
pip install shipcadence
shipcadence analyze owner/repo --token ghp_xxx
```

Instant DORA metrics. No Docker, Grafana, or database server required.

## What it measures

| Metric | Description | Elite | High | Medium | Low |
|--------|-------------|-------|------|--------|-----|
| **Deployment Frequency** | How often code is deployed | >= 1/day | >= 1/week | >= 1/month | < 1/month |
| **Lead Time for Changes** | PR merge to production deploy | < 1 day | < 1 week | < 1 month | > 1 month |
| **Change Failure Rate** | % of deploys causing incidents | <= 5% | <= 10% | <= 15% | > 15% |
| **Mean Time to Restore** | Time to recover from failures | < 1 hour | < 1 day | < 1 week | > 1 week |

## Quick Start

### Install

```bash
pip install shipcadence
```

### Analyze a repository

```bash
# With an explicit token
shipcadence analyze owner/repo --token ghp_xxx

# Using GITHUB_TOKEN env var
export GITHUB_TOKEN=ghp_xxx
shipcadence analyze owner/repo

# Store token securely (encrypted, persisted)
shipcadence config set-token ghp_xxx
shipcadence analyze owner/repo
```

### Output formats

```bash
shipcadence analyze owner/repo --format table     # default, coloured terminal table
shipcadence analyze owner/repo --format json      # machine-readable JSON
shipcadence analyze owner/repo --format markdown  # copy into PRs/wikis
```

### Scheduled collection

```bash
# Run daily at 2am (default)
shipcadence watch owner/repo --schedule "0 2 * * *"

# With webhook alerts when metrics degrade
shipcadence watch owner/repo --webhook https://hooks.slack.com/services/T.../B.../xxx
```

### Multi-repo comparison

```bash
shipcadence analyze acme/api acme/web acme/worker --token ghp_xxx
```

### Trend comparison

```bash
# Compare current 30 days vs previous 30 days
shipcadence analyze owner/repo --days 30 --compare
```

## CLI Reference

```
shipcadence --version
shipcadence --help

shipcadence analyze <owner/repo> [owner/repo2 ...]
    --token TEXT      GitHub PAT (or set GITHUB_TOKEN / use config set-token)
    --days INT        Analysis window in days [default: 90]
    --format TEXT     Output format: table|json|markdown [default: table]
    --compare         Compare current period vs previous period

shipcadence watch <owner/repo>
    --token TEXT      GitHub PAT
    --days INT        Analysis window [default: 90]
    --schedule TEXT   Cron expression [default: "0 2 * * *"]
    --webhook URL     Webhook for alert notifications

shipcadence config set-token <TOKEN>     Encrypt and store GitHub PAT
shipcadence config show-token            Show stored token (masked)
shipcadence config delete-token          Delete stored token
```

## Architecture

ShipCadence uses [Dagloom](https://github.com/lucientong/dagloom) to orchestrate data collection, transformation, and computation as a DAG pipeline:

```
fetch_pulls ────────┐
fetch_deployments ──┤
fetch_issues ───────┤──► transform_all ──► compute_metrics ──► format_report
pass_config ────────┘
```

**Key Dagloom features used:**

- `@node(retry=3, cache=True, timeout=30)` — resilient GitHub API calls with caching
- `parallel()` + `>>` operator — declarative fan-out/fan-in DAG construction
- `AsyncExecutor` — concurrent fetch execution
- `SecretStore` — encrypted GitHub token storage
- `SchedulerService` — cron-based scheduled collection
- `Pipeline.notify_on` — webhook/email alerts when metrics degrade

### Data flow

1. **Fetch** — Three async nodes call the GitHub API in parallel (PRs, Deployments, Issues)
2. **Transform** — Fan-in node normalises raw API data and correlates PRs to deployments
3. **Compute** — Calculates all four DORA metrics with benchmark ratings
4. **Report** — Formats output for display (table, JSON, or Markdown)

## Development

```bash
git clone https://github.com/lucientong/shipcadence.git
cd shipcadence
python -m venv venv && source venv/bin/activate
pip install -e ".[dev]"

# Run tests
pytest

# Lint + format
ruff check shipcadence/ tests/
ruff format --check shipcadence/ tests/
```

## Project Structure

```
shipcadence/
├── __init__.py
├── cli.py                   # Click CLI entry point
├── config.py                # Configuration management
├── models.py                # Data models (dataclasses)
├── secrets.py               # SecretStore integration
├── report.py                # JSON/Markdown export
├── pipelines/
│   ├── collect.py           # Main DORA pipeline assembly
│   └── alert.py             # Alert pipeline with thresholds
└── nodes/
    ├── github.py            # GitHub API collection nodes
    ├── transforms.py        # Data normalisation + correlation
    ├── metrics.py           # DORA computation + ratings
    └── alerts.py            # Threshold checking + report formatting
```

## License

Apache License 2.0 — see [LICENSE](LICENSE).
