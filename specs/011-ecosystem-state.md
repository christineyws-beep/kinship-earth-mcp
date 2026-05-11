# Spec 011: Ecosystem State Continuous Monitoring

> Phase 5.1 — Continuous Monitoring
> Priority: P0 (foundation for anomaly detection)
> Estimated effort: 1 session
> Dependency: Specs 006-010 (graph infrastructure, memory tools, ranking) — all done

## Objective

Implement continuous `EcosystemState` computation for monitored locations. Build baseline calculation from ERA5 climate normals + USGS streamflow + NEON biological signals. Create an `ecology_ecosystem_state` tool that returns the current state vector for any location, and a monitoring registry that tracks which locations are being actively monitored.

## What to Build

### 1. Baseline Calculator

Create `shared/src/kinship_shared/baselines.py`:

```python
"""
Baseline computation for ecosystem monitoring.

Computes historical normals from ERA5 (climate), USGS NWIS (hydrology),
and NEON (biology) to establish what 'normal' looks like for a location
at a given time of year. Baselines are the reference against which
anomalies are detected.
"""

from __future__ import annotations

import math
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class BaselineValues(BaseModel):
    """Historical normal values for a location at a specific day-of-year.

    Computed from multi-year data. Each value is the mean for a 15-day
    window centered on the target day-of-year.
    """

    location_id: str = Field(description="Ecosystem identifier, e.g. 'watershed:russian-river'")
    day_of_year: int = Field(ge=1, le=366, description="Day of year the baseline is for")
    years_of_data: int = Field(default=0, description="Number of years used to compute baseline")

    # Climate baselines (from ERA5)
    temp_mean_c: Optional[float] = Field(default=None, description="30-year mean temperature for this DOY")
    temp_std_c: Optional[float] = Field(default=None, description="Standard deviation of temperature")
    precip_mean_mm: Optional[float] = Field(default=None, description="Mean daily precipitation for this DOY")
    precip_std_mm: Optional[float] = Field(default=None, description="Std dev of daily precipitation")

    # Hydrology baselines (from USGS)
    streamflow_mean_cfs: Optional[float] = Field(default=None, description="Mean streamflow for this DOY")
    streamflow_std_cfs: Optional[float] = Field(default=None, description="Std dev of streamflow")

    # Biology baselines (from NEON / eBird / GBIF)
    species_richness_mean: Optional[int] = Field(default=None, description="Mean species count for this DOY window")
    ndvi_mean: Optional[float] = Field(default=None, description="Mean NDVI for this DOY")
    ndvi_std: Optional[float] = Field(default=None, description="Std dev of NDVI")


def compute_deviation(current: float, baseline_mean: float, baseline_std: float) -> float:
    """Compute normalized deviation from baseline.

    Returns a value in approximately [-3, 3] (z-score). Values beyond +/-2
    are unusual; beyond +/-3 are extreme.

    If baseline_std is zero or very small, caps the deviation at +/-3.
    """
    if baseline_std is None or baseline_std < 1e-6:
        # Can't compute z-score without std dev — use sign only
        diff = current - baseline_mean
        return max(-3.0, min(3.0, diff / max(abs(baseline_mean), 1e-6) * 3.0))
    return (current - baseline_mean) / baseline_std


def compute_health_score(deviations: list[float]) -> float:
    """Compute an overall ecosystem health score (0-100) from deviation vector.

    100 = all signals at baseline. Score decreases as signals deviate.
    Uses RMS of deviations, scaled so that 2-sigma deviation = score 50.
    """
    if not deviations:
        return 50.0  # No data — neutral score
    rms = math.sqrt(sum(d * d for d in deviations) / len(deviations))
    # Scale: rms=0 → 100, rms=2 → 50, rms=4 → 0
    score = max(0.0, min(100.0, 100.0 * (1.0 - rms / 4.0)))
    return round(score, 1)


def classify_trend(health_scores: list[float]) -> str:
    """Classify trend direction from recent health scores (most recent last).

    Expects at least 3 scores. Returns one of:
    'improving', 'stable', 'declining', 'critical'.
    """
    if len(health_scores) < 3:
        return "stable"
    recent = health_scores[-3:]
    slope = (recent[-1] - recent[0]) / 2.0

    if recent[-1] < 25:
        return "critical"
    elif slope > 3.0:
        return "improving"
    elif slope < -3.0:
        return "declining"
    return "stable"


async def compute_baselines_from_era5(
    era5_adapter,
    lat: float,
    lng: float,
    target_date: datetime,
    years_back: int = 5,
) -> BaselineValues:
    """Compute climate baselines from ERA5 historical data.

    Queries ERA5 for the same 15-day window across multiple years, then
    computes mean and std for temperature and precipitation.

    Uses years_back years of data (default 5 to stay within free API limits).
    For a true 30-year normal, increase years_back (but expect slower queries).
    """
    from .schema import SearchParams

    doy = target_date.timetuple().tm_yday
    location_id = f"location:{lat:.2f}_{lng:.2f}"
    temps: list[float] = []
    precips: list[float] = []

    for year_offset in range(1, years_back + 1):
        year = target_date.year - year_offset
        # 15-day window centered on target DOY
        from datetime import timedelta
        center = datetime(year, 1, 1) + timedelta(days=doy - 1)
        start = (center - timedelta(days=7)).strftime("%Y-%m-%d")
        end = (center + timedelta(days=7)).strftime("%Y-%m-%d")

        try:
            era5_data = await era5_adapter.get_daily(lat=lat, lng=lng, start_date=start, end_date=end)
            daily = era5_data.get("daily", {})
            if "temperature_2m_mean" in daily:
                temps.extend([v for v in daily["temperature_2m_mean"] if v is not None])
            if "precipitation_sum" in daily:
                precips.extend([v for v in daily["precipitation_sum"] if v is not None])
        except Exception:
            continue  # Skip years with missing data

    baseline = BaselineValues(
        location_id=location_id,
        day_of_year=doy,
        years_of_data=years_back,
    )

    if temps:
        baseline.temp_mean_c = sum(temps) / len(temps)
        if len(temps) > 1:
            mean = baseline.temp_mean_c
            baseline.temp_std_c = math.sqrt(sum((t - mean) ** 2 for t in temps) / (len(temps) - 1))
    if precips:
        baseline.precip_mean_mm = sum(precips) / len(precips)
        if len(precips) > 1:
            mean = baseline.precip_mean_mm
            baseline.precip_std_mm = math.sqrt(sum((p - mean) ** 2 for p in precips) / (len(precips) - 1))

    return baseline


async def compute_baselines_from_usgs(
    usgs_adapter,
    lat: float,
    lng: float,
    target_date: datetime,
    radius_km: float = 50.0,
) -> dict:
    """Compute streamflow baselines from nearby USGS gauges.

    Returns dict with streamflow_mean_cfs and streamflow_std_cfs.
    """
    from .schema import SearchParams
    from datetime import timedelta

    doy = target_date.timetuple().tm_yday
    flows: list[float] = []

    # Get recent data from nearby stations as proxy for baseline
    start = (target_date - timedelta(days=30)).strftime("%Y-%m-%d")
    end = target_date.strftime("%Y-%m-%d")

    try:
        observations = await usgs_adapter.search(
            SearchParams(lat=lat, lng=lng, radius_km=radius_km, start_date=start, end_date=end, limit=100)
        )
        for obs in observations:
            if obs.value and isinstance(obs.value, dict):
                flow = obs.value.get("discharge_cfs") or obs.value.get("value")
                if flow is not None:
                    try:
                        flows.append(float(flow))
                    except (ValueError, TypeError):
                        continue
    except Exception:
        pass

    result = {}
    if flows:
        result["streamflow_mean_cfs"] = sum(flows) / len(flows)
        if len(flows) > 1:
            mean = result["streamflow_mean_cfs"]
            result["streamflow_std_cfs"] = math.sqrt(sum((f - mean) ** 2 for f in flows) / (len(flows) - 1))
    return result
```

### 2. Monitoring Site Registry

Create `shared/src/kinship_shared/monitoring.py`:

```python
"""
Monitoring site registry — tracks which locations are actively monitored.

Sites can be added manually or auto-registered when a location is queried
repeatedly. Each site maintains its latest EcosystemState and baseline.
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import aiosqlite
from pydantic import BaseModel, Field

from .schema import EcosystemState, Location

logger = logging.getLogger(__name__)

_DEFAULT_DB_DIR = Path.home() / ".kinship-earth"
_DEFAULT_DB_PATH = _DEFAULT_DB_DIR / "monitoring.db"


class MonitoringSite(BaseModel):
    """A location being actively monitored for ecosystem state changes."""

    site_id: str = Field(description="Unique site ID, e.g. 'watershed:russian-river'")
    name: str = Field(description="Human-readable name")
    location: Location
    enabled: bool = Field(default=True)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    last_checked: Optional[datetime] = Field(default=None)
    check_interval_hours: int = Field(default=24, description="How often to recompute state")


_CREATE_TABLES = """
CREATE TABLE IF NOT EXISTS monitoring_sites (
    site_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    lat REAL NOT NULL,
    lng REAL NOT NULL,
    enabled INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    last_checked TEXT,
    check_interval_hours INTEGER NOT NULL DEFAULT 24,
    metadata TEXT NOT NULL DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS ecosystem_states (
    id TEXT NOT NULL,
    site_id TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    state_json TEXT NOT NULL,
    PRIMARY KEY (site_id, timestamp)
);

CREATE INDEX IF NOT EXISTS idx_states_site ON ecosystem_states(site_id);
CREATE INDEX IF NOT EXISTS idx_states_time ON ecosystem_states(timestamp);
"""


class MonitoringRegistry:
    """Manages monitored sites and their ecosystem state history."""

    def __init__(self, db_path: str | None = None):
        self._db_path = db_path or str(
            os.environ.get("KINSHIP_MONITORING_DB_PATH", _DEFAULT_DB_PATH)
        )
        self._initialized = False

    async def initialize(self) -> None:
        if self._initialized:
            return
        os.makedirs(os.path.dirname(self._db_path), exist_ok=True)
        async with aiosqlite.connect(self._db_path) as db:
            await db.executescript(_CREATE_TABLES)
            await db.commit()
        self._initialized = True

    async def add_site(self, site: MonitoringSite) -> None:
        await self.initialize()
        async with aiosqlite.connect(self._db_path) as db:
            await db.execute(
                "INSERT OR REPLACE INTO monitoring_sites (site_id, name, lat, lng, enabled, created_at, last_checked, check_interval_hours) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (site.site_id, site.name, site.location.lat, site.location.lng, int(site.enabled), site.created_at.isoformat(), site.last_checked.isoformat() if site.last_checked else None, site.check_interval_hours),
            )
            await db.commit()

    async def get_site(self, site_id: str) -> MonitoringSite | None:
        await self.initialize()
        async with aiosqlite.connect(self._db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("SELECT * FROM monitoring_sites WHERE site_id = ?", (site_id,))
            row = await cursor.fetchone()
            if not row:
                return None
            return MonitoringSite(
                site_id=row["site_id"],
                name=row["name"],
                location=Location(lat=row["lat"], lng=row["lng"]),
                enabled=bool(row["enabled"]),
                created_at=datetime.fromisoformat(row["created_at"]),
                last_checked=datetime.fromisoformat(row["last_checked"]) if row["last_checked"] else None,
                check_interval_hours=row["check_interval_hours"],
            )

    async def list_sites(self, enabled_only: bool = True) -> list[MonitoringSite]:
        await self.initialize()
        async with aiosqlite.connect(self._db_path) as db:
            db.row_factory = aiosqlite.Row
            query = "SELECT * FROM monitoring_sites"
            if enabled_only:
                query += " WHERE enabled = 1"
            cursor = await db.execute(query)
            rows = await cursor.fetchall()
            return [
                MonitoringSite(
                    site_id=row["site_id"],
                    name=row["name"],
                    location=Location(lat=row["lat"], lng=row["lng"]),
                    enabled=bool(row["enabled"]),
                    created_at=datetime.fromisoformat(row["created_at"]),
                    last_checked=datetime.fromisoformat(row["last_checked"]) if row["last_checked"] else None,
                    check_interval_hours=row["check_interval_hours"],
                )
                for row in rows
            ]

    async def remove_site(self, site_id: str) -> bool:
        await self.initialize()
        async with aiosqlite.connect(self._db_path) as db:
            cursor = await db.execute("DELETE FROM monitoring_sites WHERE site_id = ?", (site_id,))
            await db.commit()
            return cursor.rowcount > 0

    async def store_state(self, state: EcosystemState) -> None:
        await self.initialize()
        async with aiosqlite.connect(self._db_path) as db:
            await db.execute(
                "INSERT OR REPLACE INTO ecosystem_states (id, site_id, timestamp, state_json) VALUES (?, ?, ?, ?)",
                (state.id, state.id, state.timestamp.isoformat(), state.model_dump_json()),
            )
            # Update last_checked on the site
            await db.execute(
                "UPDATE monitoring_sites SET last_checked = ? WHERE site_id = ?",
                (state.timestamp.isoformat(), state.id),
            )
            await db.commit()

    async def get_latest_state(self, site_id: str) -> EcosystemState | None:
        await self.initialize()
        async with aiosqlite.connect(self._db_path) as db:
            cursor = await db.execute(
                "SELECT state_json FROM ecosystem_states WHERE site_id = ? ORDER BY timestamp DESC LIMIT 1",
                (site_id,),
            )
            row = await cursor.fetchone()
            if not row:
                return None
            return EcosystemState.model_validate_json(row[0])

    async def get_state_history(self, site_id: str, limit: int = 30) -> list[EcosystemState]:
        await self.initialize()
        async with aiosqlite.connect(self._db_path) as db:
            cursor = await db.execute(
                "SELECT state_json FROM ecosystem_states WHERE site_id = ? ORDER BY timestamp DESC LIMIT ?",
                (site_id, limit),
            )
            rows = await cursor.fetchall()
            return [EcosystemState.model_validate_json(row[0]) for row in rows]

    def site_count(self) -> int:
        """Synchronous site count from last known state."""
        import sqlite3
        try:
            conn = sqlite3.connect(self._db_path)
            cursor = conn.execute("SELECT COUNT(*) FROM monitoring_sites WHERE enabled = 1")
            count = cursor.fetchone()[0]
            conn.close()
            return count
        except Exception:
            return 0
```

### 3. Ecosystem State Builder

Create `shared/src/kinship_shared/state_builder.py`:

```python
"""
Builds an EcosystemState for a location by querying live data sources
and comparing against baselines.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

from .baselines import (
    BaselineValues,
    classify_trend,
    compute_baselines_from_era5,
    compute_baselines_from_usgs,
    compute_deviation,
    compute_health_score,
)
from .schema import EcosystemState, Location, SearchParams

logger = logging.getLogger(__name__)


async def build_ecosystem_state(
    *,
    site_id: str,
    location: Location,
    era5_adapter,
    usgs_adapter,
    neon_adapter=None,
    ebird_adapter=None,
    gbif_adapter=None,
    period_days: int = 30,
    baseline_years: int = 5,
    recent_health_scores: list[float] | None = None,
) -> EcosystemState:
    """Build a current EcosystemState for a location.

    Queries ERA5 for current climate, USGS for current hydrology,
    computes baselines, and compares to produce deviation vectors.
    """
    now = datetime.now(timezone.utc)
    from datetime import timedelta

    # 1. Get current ERA5 climate data
    end_date = now.strftime("%Y-%m-%d")
    start_date = (now - timedelta(days=period_days)).strftime("%Y-%m-%d")

    temp_mean = None
    precip_7d = None
    try:
        era5_data = await era5_adapter.get_daily(
            lat=location.lat, lng=location.lng,
            start_date=start_date, end_date=end_date,
        )
        daily = era5_data.get("daily", {})
        temps = [v for v in daily.get("temperature_2m_mean", []) if v is not None]
        if temps:
            temp_mean = sum(temps) / len(temps)

        precips = [v for v in daily.get("precipitation_sum", []) if v is not None]
        if precips:
            precip_7d = sum(precips[-7:])  # Last 7 days
    except Exception as e:
        logger.warning("ERA5 query failed for %s: %s", site_id, e)

    # 2. Get current USGS hydrology
    streamflow = None
    try:
        usgs_obs = await usgs_adapter.search(
            SearchParams(
                lat=location.lat, lng=location.lng,
                radius_km=50.0,
                start_date=(now - timedelta(days=7)).strftime("%Y-%m-%d"),
                end_date=end_date,
                limit=20,
            )
        )
        flows = []
        for obs in usgs_obs:
            if obs.value and isinstance(obs.value, dict):
                flow = obs.value.get("discharge_cfs") or obs.value.get("value")
                if flow is not None:
                    try:
                        flows.append(float(flow))
                    except (ValueError, TypeError):
                        continue
        if flows:
            streamflow = sum(flows) / len(flows)
    except Exception as e:
        logger.warning("USGS query failed for %s: %s", site_id, e)

    # 3. Get species richness (from eBird/GBIF if available)
    species_richness = None
    if ebird_adapter or gbif_adapter:
        try:
            adapter = ebird_adapter or gbif_adapter
            bio_obs = await adapter.search(
                SearchParams(
                    lat=location.lat, lng=location.lng,
                    radius_km=25.0,
                    start_date=(now - timedelta(days=period_days)).strftime("%Y-%m-%d"),
                    end_date=end_date,
                    limit=200,
                )
            )
            species_names = set()
            for obs in bio_obs:
                if obs.taxon and obs.taxon.scientific_name:
                    species_names.add(obs.taxon.scientific_name)
            species_richness = len(species_names) if species_names else None
        except Exception as e:
            logger.warning("Biology query failed for %s: %s", site_id, e)

    # 4. Compute baselines
    baseline = await compute_baselines_from_era5(era5_adapter, location.lat, location.lng, now, years_back=baseline_years)
    usgs_baseline = await compute_baselines_from_usgs(usgs_adapter, location.lat, location.lng, now)

    # 5. Compute deviations
    deviations = []
    temp_anomaly = None

    if temp_mean is not None and baseline.temp_mean_c is not None:
        temp_anomaly = temp_mean - baseline.temp_mean_c
        d = compute_deviation(temp_mean, baseline.temp_mean_c, baseline.temp_std_c or 2.0)
        deviations.append(max(-1.0, min(1.0, d / 3.0)))  # Normalize to [-1, 1]

    streamflow_baseline = usgs_baseline.get("streamflow_mean_cfs")
    if streamflow is not None and streamflow_baseline is not None:
        std = usgs_baseline.get("streamflow_std_cfs", streamflow_baseline * 0.3)
        d = compute_deviation(streamflow, streamflow_baseline, std)
        deviations.append(max(-1.0, min(1.0, d / 3.0)))

    # 6. Compute health score and trend
    health = compute_health_score(deviations)

    health_history = list(recent_health_scores or [])
    health_history.append(health)
    trend = classify_trend(health_history)

    sources = []
    if temp_mean is not None:
        sources.append("era5")
    if streamflow is not None:
        sources.append("usgs-nwis")
    if species_richness is not None:
        sources.append("ebird" if ebird_adapter else "gbif")

    return EcosystemState(
        id=site_id,
        location=location,
        timestamp=now,
        period_days=period_days,
        streamflow_cfs=streamflow,
        streamflow_baseline=streamflow_baseline,
        precipitation_7d_mm=precip_7d,
        species_richness=species_richness,
        species_baseline=baseline.species_richness_mean,
        temp_mean_c=temp_mean,
        temp_anomaly_c=temp_anomaly,
        deviation_vector=deviations,
        overall_health_score=health,
        trend_direction=trend,
        sources_contributing=sources,
        last_updated=now,
    )
```

### 4. MCP Tool: `ecology_ecosystem_state`

Add to `servers/orchestrator/src/kinship_orchestrator/server.py`:

```python
@mcp.tool()
async def ecology_ecosystem_state(
    lat: float,
    lng: float,
    site_name: str | None = None,
    period_days: int = 30,
) -> dict:
    """Get the current ecosystem state for a location.

    Computes a multi-signal state vector combining climate (ERA5),
    hydrology (USGS), and biodiversity data. Returns health score,
    deviation from baseline, and trend direction.

    Use this to understand the current ecological condition at a location
    and whether it's within normal ranges.
    """
```

This tool should:
- Build an `EcosystemState` using `build_ecosystem_state()`
- If a monitoring site exists for this location, use stored history for trend
- If no monitoring site exists but `site_name` is provided, auto-register it
- Return the state as a dict with visualization hint `"dashboard"`
- Store the state in the monitoring registry

### 5. MCP Tool: `ecology_monitor_site`

Add to the orchestrator:

```python
@mcp.tool()
async def ecology_monitor_site(
    action: Literal["add", "remove", "list"],
    lat: float | None = None,
    lng: float | None = None,
    site_name: str | None = None,
    site_id: str | None = None,
) -> dict:
    """Manage monitored ecosystem sites.

    - add: Register a new location for continuous monitoring
    - remove: Stop monitoring a location
    - list: Show all monitored sites with their latest health scores
    """
```

### 6. Wire Into Orchestrator

Modify `servers/orchestrator/src/kinship_orchestrator/server.py`:
- Import `MonitoringRegistry`, `build_ecosystem_state`
- Initialize `_monitoring = MonitoringRegistry()`
- Add lazy initialization with `_ensure_monitoring()`
- Register both new tools
- Update tool count expectation (17 → 19)

## What NOT to Build

- No scheduled cron jobs (scheduled monitoring is spec 013 territory — for now, state is computed on-demand)
- No anomaly detection yet (that's spec 012)
- No event synthesis (that's spec 013)
- No NDVI/spectral baselines (need Copernicus adapter first)
- No proactive notifications (future milestone)

## Tests to Write

Create `shared/tests/test_baselines.py`:

1. `test_compute_deviation_normal` — value at baseline returns ~0
2. `test_compute_deviation_extreme` — value 3 sigma above returns ~3
3. `test_compute_deviation_zero_std` — handles zero std gracefully
4. `test_compute_health_score_all_normal` — deviations near 0 → score near 100
5. `test_compute_health_score_all_extreme` — large deviations → score near 0
6. `test_classify_trend_improving` — rising health scores → "improving"
7. `test_classify_trend_declining` — falling health scores → "declining"
8. `test_classify_trend_critical` — very low score → "critical"
9. `test_classify_trend_stable` — flat scores → "stable"

Create `shared/tests/test_monitoring.py`:

10. `test_add_and_get_site` — round-trip site to registry
11. `test_list_sites` — add multiple sites, list returns all
12. `test_remove_site` — remove a site, verify it's gone
13. `test_store_and_get_state` — store an EcosystemState, retrieve it
14. `test_state_history` — store multiple states, get ordered history
15. `test_latest_state` — verify get_latest_state returns most recent

Create `servers/orchestrator/tests/test_ecosystem_state.py`:

16. `test_ecosystem_state_tool_registered` — verify ecology_ecosystem_state is in mcp tools
17. `test_monitor_site_tool_registered` — verify ecology_monitor_site is in mcp tools

## Verification

```bash
# Baseline math tests (offline, no network)
uv run --package kinship-orchestrator pytest shared/tests/test_baselines.py -v

# Monitoring registry tests (offline, SQLite only)
uv run --package kinship-orchestrator pytest shared/tests/test_monitoring.py -v

# Tool registration tests
uv run --package kinship-orchestrator pytest servers/orchestrator/tests/test_ecosystem_state.py -v

# All existing tests still pass (offline subset)
uv run --package kinship-orchestrator pytest servers/orchestrator/tests/ shared/tests/ -v -k "not (climate or dolphin or cetac or wind_river or woods_hole or parallel or cross_persona or marine or reachable or coordinates or geographic or bird_survey or bird_data or catalog or nonexistent or empty_area or bogus)"

# Server loads with correct counts
uv run --package kinship-orchestrator python -c "from kinship_orchestrator.server import mcp; print(f'Tools: {len(mcp._tool_manager._tools)}')"
# Expected: Tools: 19 (was 17 + ecology_ecosystem_state + ecology_monitor_site)
```

## Commit Message Template

```
Add ecosystem state computation and monitoring registry

Implements Phase 5.1 continuous monitoring:
- BaselineValues model and compute_deviation/health_score/classify_trend
- compute_baselines_from_era5 and compute_baselines_from_usgs
- MonitoringRegistry with SQLite persistence
- build_ecosystem_state: multi-source state vector builder
- ecology_ecosystem_state tool: on-demand state for any location
- ecology_monitor_site tool: manage monitored locations
- 17 new tests

Spec: specs/011-ecosystem-state.md
```

## Files to Create/Modify

| Action | File |
|--------|------|
| Create | `shared/src/kinship_shared/baselines.py` |
| Create | `shared/src/kinship_shared/monitoring.py` |
| Create | `shared/src/kinship_shared/state_builder.py` |
| Create | `shared/tests/test_baselines.py` |
| Create | `shared/tests/test_monitoring.py` |
| Create | `servers/orchestrator/tests/test_ecosystem_state.py` |
| Modify | `shared/src/kinship_shared/__init__.py` (export new classes) |
| Modify | `servers/orchestrator/src/kinship_orchestrator/server.py` (add tools + monitoring) |
| Modify | `specs/QUEUE.md` (mark this spec done) |
| Modify | `ROADMAP.md` (check off Milestone 5.1 items) |
