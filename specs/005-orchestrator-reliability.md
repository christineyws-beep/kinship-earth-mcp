# 005: Orchestrator Reliability — Timeouts + Retry + Graceful Degradation

**Branch:** `sprint/orchestrator-reliability`
**Est:** 1-2 hours
**Dependencies:** None

## Context

The orchestrator queries up to 10 adapters in parallel for cross-source queries. If any adapter is slow or down, it can degrade the entire response. This spec adds proper timeout handling, per-adapter retry logic, and graceful degradation (return partial results from healthy adapters).

## Current State

- Orchestrator uses `asyncio.gather()` for parallel queries
- Some adapters have retry logic (added in prior burndown)
- No per-adapter timeout enforcement at the orchestrator level
- If one adapter hangs, the whole query blocks

## Boundaries

**Always:** Return partial results when some adapters fail. Log which adapters timed out.
**Ask first:** Default timeout values (proposed: 8s per adapter, 15s total).
**Never:** Silently drop errors. Retry more than 2 times per adapter.

## Steps

### 1. Audit current timeout/retry state
- Check each adapter for existing timeout handling
- Check orchestrator's `asyncio.gather()` calls for timeout params
- Document current behavior in a comment

### 2. Add per-adapter timeout wrapper
```python
async def query_with_timeout(adapter, params, timeout_seconds=8):
    try:
        return await asyncio.wait_for(adapter.search(params), timeout=timeout_seconds)
    except asyncio.TimeoutError:
        logger.warning(f"{adapter.id} timed out after {timeout_seconds}s")
        return []  # graceful degradation
    except Exception as e:
        logger.error(f"{adapter.id} failed: {e}")
        return []
```

### 3. Add response metadata
Include in orchestrator response:
- `sources_queried: list[str]` — which adapters were called
- `sources_succeeded: list[str]` — which returned data
- `sources_failed: list[str]` — which timed out or errored
- `query_time_ms: int` — total wall clock time

### 4. Add retry for transient failures
- Retry once on connection errors or 5xx responses
- No retry on 4xx (client error) or timeout (already slow)
- Exponential backoff: 1s between retries

### 5. Write tests
- [ ] `test_orchestrator_survives_one_adapter_down` — mock one adapter to raise, verify others return
- [ ] `test_timeout_returns_partial_results` — mock one adapter to sleep(30), verify response within 15s
- [ ] `test_response_metadata_includes_failed_sources` — verify sources_failed is populated
- [ ] `test_all_adapters_healthy` — normal case, all sources_succeeded

### 6. Full test suite
```bash
uv run pytest -v
```

## Success Criteria
- No single adapter can block the entire query
- Response metadata shows which sources succeeded/failed
- Partial results returned when some adapters are down
- All existing tests pass
- Total query time stays under 15s
