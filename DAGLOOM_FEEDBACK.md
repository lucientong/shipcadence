# Dagloom Feedback from ShipCadence

## Blockers (must be fixed before continuing)

_None._

## Pain Points (can work around but poor experience)

### FB-001: `>>` operator cannot express fan-out / fan-in DAGs
- **Scenario**: ShipCadence needs 3 independent fetch nodes (pulls, deployments, issues) fanning into a single transform node. This is a common ETL pattern.
- **Workaround**: Used `Pipeline.add_node()` / `add_edge()` to build the DAG programmatically instead of `>>`.
- **Suggestion**: Add a `parallel()` or `merge()` helper, e.g. `parallel(fetch_pulls, fetch_deployments, fetch_issues) >> transform_all`, so fan-out/fan-in DAGs can be expressed declaratively.
- **Status**: FIXED (by dagloom v1.0.1) -- `parallel()` helper added; ShipCadence now uses `parallel(fetch_pulls, fetch_deployments, fetch_issues, pass_config) >> transform_all >> compute_metrics >> format_report`.

### FB-002: Root nodes receive ALL `**inputs` — no parameter filtering
- **Scenario**: All root nodes receive every kwarg passed to `pipeline.run()`. Our `pass_config` node only needs `days` but also receives `owner`, `repo`, `token`. Had to add `**_kwargs` to avoid `TypeError`.
- **Workaround**: Added `**_kwargs: Any` to the node signature to absorb extra keyword arguments.
- **Suggestion**: Filter `**inputs` to only pass kwargs that match each root node's parameter signature (via `inspect.signature`). This would make node signatures cleaner and catch typos.
- **Status**: FIXED (by dagloom v1.0.1) -- `_filter_inputs()` now filters kwargs by parameter signature; `**_kwargs` workaround removed from `pass_config`.

### FB-003: Non-root nodes cannot access original pipeline inputs
- **Scenario**: The `transform_all` node (non-root, multiple predecessors) needs the `days` config value, but it only receives a dict of predecessor outputs — not the original `**inputs`.
- **Workaround**: Created a trivial `pass_config` root node that forwards `days` through the DAG so `transform_all` can read it from the predecessor dict.
- **Suggestion**: Either (a) pass original inputs as a second argument to all nodes, or (b) make `ExecutionContext` accessible to node functions so they can read pipeline-level config.
- **Status**: FIXED (by dagloom v1.0.1) -- `ExecutionContext` now stores `pipeline_inputs` and provides `get_input(key)`. Note: context is not yet injected into node functions automatically, so the `pass_config` bridge node is still used. Future improvement: auto-inject context when a node declares a parameter typed `ExecutionContext`.

## Nice to Have (improvement suggestions)

### FB-004: Document multi-predecessor input shape more prominently
- **Suggestion**: The fact that nodes with multiple predecessors receive `{predecessor_name: output}` as a positional dict is critical for pipeline design but only documented in docstrings deep in `pipeline.py`. Add a prominent section in the getting-started guide with an example.
- **Status**: FIXED (by dagloom v1.0.1) -- `Pipeline.run()` docstring improved with clear documentation of the multi-predecessor dict shape.

### FB-005: `Pipeline.visualize()` could show node metadata
- **Suggestion**: `visualize()` currently shows names and edges. It would be helpful to also show `retry`, `cache`, `timeout` settings per node for debugging pipeline configuration.
- **Status**: FIXED (by dagloom v1.0.1) -- `visualize()` now displays retry, cache, timeout, and executor settings per node.
